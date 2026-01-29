
import sys
import asyncio
from threading import Thread, Event
from queue import Queue
from time import sleep, time
import signal
from functools import partial
import socket
import fcntl
import struct

from pysnmp.entity import engine, config
from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto import api

from easysnmp import Session
import traceback

from .utils import log

# Compatibility helpers for pysnmp vs pysnmp-lextudio naming.
def _get_method(obj, snake, camel):
    fn = getattr(obj, snake, None)
    if fn is not None:
        return fn
    fn = getattr(obj, camel, None)
    if fn is not None:
        return fn
    raise AttributeError(f'{type(obj).__name__} has no {snake} or {camel}')

# pysnmp-lextudio no longer supports allow_broadcast in openClientMode.
# Set SO_BROADCAST on the underlying socket once the transport is created.
class _BroadcastUdpAsyncioTransport(udp.UdpAsyncioTransport):
    def connection_made(self, transport):
        try:
            sock = transport.get_extra_info("socket")
            if sock is not None:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except Exception as e:
            log(f'_BroadcastUdpAsyncioTransport: failed to set SO_BROADCAST: {e}', )
        super().connection_made(transport)

# Broadcast manager settings
maxWaitForResponses = 5
maxNumberResponses = 20


# SNMP Broadcast discovery thread  
# This thread will broadcast a SNMP request to all devices on the network
# to get the hostname, system description, MAC address and serial number.
# 
# This is the initial device discovery thread that will populate the device
# list with the devices found on the network.
# 
# See snmpThread.py for the SNMP thread that will poll the devices for status
# of the operating devices.
#
# Currently this is used to discover:
#   - Brother QL Label printers
#   - Impinj RFID readers
#

# This called with the api version to use, v1 or v2c. It cannot do both at the same time.
# This will find all of the active network interfaces that start with "enp" or "wlp" 
# and alternate discovery across the ones that are found.
class DiscoveryThread(Thread, ):

    hostname = "1.3.6.1.2.1.1.5.0"              # Hostname
    sysDescr = "1.3.6.1.2.1.1.1.0"              # System Description

    sysUpTime = "1.3.6.1.2.1.1.3.0"

    # recent devices should have MACAddress
    # older Brother printers do not have MACAddress, but have SerialNumber
    # and only support api1

    MACAddress = "1.3.6.1.2.1.2.2.1.6.2"        # MRVINREACH-MIB::ifPhysAddress.2
    SerialNumber = "1.3.6.1.2.1.43.5.1.1.17.1"  # Printer-MIB::prtGeneralSerialNumber.1
    ap1_oids = [ sysUpTime, SerialNumber, hostname, sysDescr, ]
    ap2c_oids = [ sysUpTime, SerialNumber, hostname, sysDescr, MACAddress, ] 
    #ap1_oids = [ sysUpTime, sysDescr, ]
    #ap2c_oids = [ sysUpTime, sysDescr, ] 


    def __init__(self, name=None, av=None, snmpDiscoveredQueue=None, stopEvent=None, changeEvent=None, **kwargs):
        #log('Discovery: snmpDiscoveredQueue: %s' % (snmpDiscoveredQueue), )

        self.av = av
        self.snmpDiscoveredQueue = snmpDiscoveredQueue
        if not self.snmpDiscoveredQueue:
            raise Exception('DiscoveryThread: snmpDiscoveredQueue is None')

        super(DiscoveryThread, self).__init__(name=name, kwargs=kwargs)
        self.name = name
        self.stopEvent = stopEvent
        self.changeEvent = changeEvent
        self.snmpEngine = engine.SnmpEngine()

        self.pMods = {}
        self.reqMsgs = {}
        self._warned_no_nic = False

        if hasattr(api, "PROTOCOL_MODULES"):
            proto_map = api.PROTOCOL_MODULES
            v1_key = api.SNMP_VERSION_1
            v2c_key = api.SNMP_VERSION_2C
        else:
            proto_map = api.protoModules
            v1_key = api.protoVersion1
            v2c_key = api.protoVersion2c

        for sav, oids, pMod in [
                ('v1', self.ap1_oids, proto_map[v1_key]),
                ('v2c', self.ap2c_oids, proto_map[v2c_key])
        ]:
            if sav != self.av:
                continue

            # Build PDU
            reqPDU = pMod.GetRequestPDU()
            # XXX pMod.apiPDU.setDefaults(reqPDU)
            pdu_set_defaults = _get_method(pMod.apiPDU, "set_defaults", "setDefaults")
            pdu_set_defaults(reqPDU)
            oidList = [(oid, pMod.Null("")) for oid in oids]
            #pMod.apiPDU.setVarBinds( reqPDU, oidList,)
            pdu_set_varbinds = _get_method(pMod.apiPDU, "set_varbinds", "setVarBinds")
            pdu_set_varbinds(reqPDU, oidList)
            #pMod.apiPDU.setRequestID(reqPDU, pMod.getNextRequestID())
            pdu_set_request_id = _get_method(pMod.apiPDU, "set_request_id", "setRequestID")
            pdu_set_request_id(reqPDU, pMod.getNextRequestID())

            # Build message
            reqMsg = pMod.Message()
            #pMod.apiMessage.setDefaults(reqMsg)
            #pMod.apiMessage.setCommunity(reqMsg, "public")
            #pMod.apiMessage.setPDU(reqMsg, reqPDU)
            msg_set_defaults = _get_method(pMod.apiMessage, "set_defaults", "setDefaults")
            msg_set_defaults(reqMsg)
            msg_set_community = _get_method(pMod.apiMessage, "set_community", "setCommunity")
            msg_set_community(reqMsg, "public")
            msg_set_pdu = _get_method(pMod.apiMessage, "set_pdu", "setPDU")
            msg_set_pdu(reqMsg, reqPDU)

            self.pMods[sav] = pMod
            self.reqMsgs[sav] = reqMsg

    def get_ip_address(self, NICname ):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            return socket.inet_ntoa(fcntl.ioctl(
               s.fileno(),
               0x8915,  # SIOCGIFADDR
               struct.pack('256s', NICname[:15].encode("UTF-8"))
            )[20:24])
        except OSError as e:
            return None

    def nic_info(self):
        nic = []
        try:
            for ix in socket.if_nameindex():
                name = ix[1]
                # XXX what is wifi prefix for Linux?
                # add wifi and ethernet interfaces
                if not name.startswith(('enp','wlp','eno','ens','enx','eth')):
                    continue
                ip = self.get_ip_address( name )
                if ip:
                    nic.append( (name, ip) )
        except Exception as e:
            log(f'nic_info: Exception: {e}', )
            log(traceback.format_exc())
      
        if not nic and not self._warned_no_nic:
            log('nic_info: no matching interfaces found', )
            self._warned_no_nic = True
        return nic

    # noinspection PyUnusedLocal,PyUnusedLocal
    def cbRecvFun(self, tav, transportDispatcher, transportDomain, transportAddress, wholeMsg, reqPDU=None):
        #log(f'cbRecvFun[{tav}:{transportAddress[0]}] wholeMsg: {wholeMsg}', )
        hostname = None
        sysDescr = None
        macAddress = None
        while wholeMsg:
            pmod = self.pMods[tav]
            rspMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=pmod.Message())
            msg_get_pdu = _get_method(pmod.apiMessage, "get_pdu", "getPDU")
            rspPDU = msg_get_pdu(rspMsg)
            pdu_get_request_id = _get_method(pmod.apiPDU, "get_request_id", "getRequestID")
            rspPDURequestID = pdu_get_request_id(rspPDU)
            # Check for SNMP errors reported
            pdu_get_error_status = _get_method(pmod.apiPDU, "get_error_status", "getErrorStatus")
            errorStatus = pdu_get_error_status(rspPDU)
            serialNumber = macAddress = hostname = sysDescr = None
            if not errorStatus:
                pdu_get_varbinds = _get_method(pmod.apiPDU, "get_varbinds", "getVarBinds")
                for oid, val in pdu_get_varbinds(rspPDU):
                    match str(oid):
                        case self.SerialNumber:
                            #log(f'cbRecvFun[{tav}:{transportAddress[0]}]SERIALNUMBER {val}', )
                            serialNumber = val
                            #log(f'cbRecvFun[{tav}:{transportAddress[0]}] SERIALNUMBER {serialNumber}', )
                        case self.MACAddress:
                            macAddress = val.prettyPrint()
                            #log(f'cbRecvFun[{tav}:{transportAddress[0]}] MACADDRESS {macAddress}', )
                        case self.hostname:
                            hostname = val.prettyPrint()
                            #log(f'cbRecvFun[{tav}:{transportAddress[0]}] HOSTNAME {hostname}', )
                        case self.sysDescr:
                            sysDescr = val.prettyPrint()
                            #log(f'cbRecvFun[{tav}:{transportAddress[0]}] SYSDESCR {sysDescr}', )
                        case _:
                            #log(f'cbRecvFun[{tav}:{transportAddress[0]}] oid unknown: %s' % oid, )
                            pass

                    #log(f"cbRecvFun[{tav}:{transportAddress[0]}] {oid.prettyPrint()} = {val.prettyPrint()}", )
                if hostname or sysDescr:
                    self.snmpDiscoveredQueue.put((transportAddress[0], hostname, sysDescr, macAddress, serialNumber, ))
                    self.changeEvent.set()
                try:
                    disp_job_finished = _get_method(transportDispatcher, "job_finished", "jobFinished")
                    disp_job_finished(1)
                except KeyError:
                    # More responses than maxNumberResponses; ignore extra.
                    pass
            else:
                log('cbRecvFun[%s:%s] errorStatus: %s' % (tav, transportAddress[0], errorStatus.prettyPrint()), )
                continue
        return wholeMsg

    def broadcast_agent_discovery(self, ):

        #log(f'{self.name}: broadcast_agent_discovery', )
        while not self.stopEvent.is_set():
            # get the network interfaces, these may change over time, e.g. wifi
            #
            nics = self.nic_info()
            #log(f'{self.name}: nics: {nics}', )
            for j, (av, reqMsg) in enumerate(self.reqMsgs.items()):
                for i, (nic, address) in enumerate(nics):
                    #log(f'{self.name}: {av} {nic} {address}', )
                    iface = (address, 0)
                    #log(f'{self.name}: AsyncioDispatcher', )
                    transportDispatcher = AsyncioDispatcher()
                    #log(f'{self.name}: registerRecvCbFun', )
                    try:
                        disp_register_recv = _get_method(transportDispatcher, "register_recv_callback", "registerRecvCbFun")
                        disp_register_recv(partial(self.cbRecvFun, av))
                    except Exception as e:
                        log(f'broadcast_agent_discover: {self.name}: Exception: {e}', )
                        log(traceback.format_exc())
                        break

                    # UDP/IPv4
                    udpSocketTransport = _BroadcastUdpAsyncioTransport().openClientMode(iface=iface)
                    domain_name = getattr(udp, "DOMAIN_NAME", getattr(udp, "domainName"))
                    disp_register_transport = _get_method(transportDispatcher, "register_transport", "registerTransport")
                    disp_register_transport(domain_name, udpSocketTransport)

                    # Pass message to dispatcher
                    target = ("255.255.255.255", 161)
                    disp_send_message = _get_method(transportDispatcher, "send_message", "sendMessage")
                    disp_send_message(encoder.encode(reqMsg), domain_name, target)

                    # wait for a maximum of responses or time out
                    disp_job_started = _get_method(transportDispatcher, "job_started", "jobStarted")
                    disp_job_started(1, maxNumberResponses)

                    # Dispatcher will finish as all jobs counter reaches zero
                    try:
                        if hasattr(transportDispatcher, "run_dispatcher"):
                            transportDispatcher.run_dispatcher(maxWaitForResponses)
                        else:
                            # lextudio AsyncioDispatcher ignores timeout; stop the loop ourselves
                            transportDispatcher.loop.call_later(maxWaitForResponses, transportDispatcher.loop.stop)
                            transportDispatcher.runDispatcher(maxWaitForResponses)
                    except Exception as e:
                        log(f'broadcast_agent_discover: {self.name}: Exception: {e}', )
                        log(traceback.format_exc())
                        raise
                    finally:
                        pass
                    disp_close = _get_method(transportDispatcher, "close_dispatcher", "closeDispatcher")
                    disp_close()

    def run(self):

        while not self.stopEvent.is_set():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.broadcast_agent_discovery())
            except Exception as e:
                log(f'Discover.run: {self.name}: Exception: {e}')
                #log(traceback.format_exc())
            log(f'Discover.run: {self.name}: loop finished', )
            loop.stop()
            loop.close()
            sleep(1)
            break


def discoveryMain():
    changeEvent = Event()
    stopEvent = Event()
    def sigintHandler(signal, frame):
        log('SIGINT received %s' % (signal,), )
        stopEvent.set()
        changeEvent.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    snmpDiscoveredQueue = Queue()        # queue for SNMP discovery
    log('discoveryMain: starting threads', )
    threads = {}
    if False:
        threads['discoveryv1'] = DiscoveryThread(name='broadcast_agent_discovery v1', av='v1',
                                       changeEvent=changeEvent, stopEvent=stopEvent, 
                                       snmpDiscoveredQueue=snmpDiscoveredQueue)

    threads['discoverv2'] = DiscoveryThread(name='broadcast_agent_discoveryv2c', av='v2c',
                                   changeEvent=changeEvent, stopEvent=stopEvent, 
                                   snmpDiscoveredQueue=snmpDiscoveredQueue)

    log('discoveryMain: starting threads', )
    [v.start() for k, v in threads.items()]

    while not stopEvent.is_set():
        while not snmpDiscoveredQueue.empty():
            hostaddr, hostname, sysdescr, macAddress, serialNumber = snmpDiscoveredQueue.get()
        sleep(2)


    pass

if __name__ == '__main__':
    discoveryMain()
