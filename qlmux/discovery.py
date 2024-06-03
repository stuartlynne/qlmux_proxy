
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

    # recent devices should have MACAddress
    # older Brother printers do not have MACAddress, but have SerialNumber
    # and only support api1

    MACAddress = "1.3.6.1.2.1.2.2.1.6.2"        # MRVINREACH-MIB::ifPhysAddress.2
    SerialNumber = "1.3.6.1.2.1.43.5.1.1.17.1"  # Printer-MIB::prtGeneralSerialNumber.1
    ap1_oids = [ SerialNumber, hostname, sysDescr, ]
    ap2c_oids = [ SerialNumber, hostname, sysDescr, MACAddress, ] 


    def __init__(self, name=None, av=None, snmpDiscoveredQueue=None, stopEvent=None, changeEvent=None, **kwargs):
        log('Discovery: snmpDiscoveredQueue: %s' % (snmpDiscoveredQueue), )

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

        for sav, oids, pMod in [
                ('v1', self.ap1_oids, api.protoModules[api.protoVersion1]), 
                ('v2c', self.ap2c_oids, api.protoModules[api.protoVersion2c])
        ]:
            if sav != self.av:
                continue

            # Build PDU
            reqPDU = pMod.GetRequestPDU()
            pMod.apiPDU.setDefaults(reqPDU)
            oidList = [(oid, pMod.Null("")) for oid in oids]
            pMod.apiPDU.setVarBinds( reqPDU, oidList,)
            pMod.apiPDU.setRequestID(reqPDU, pMod.getNextRequestID())

            # Build message
            reqMsg = pMod.Message()
            pMod.apiMessage.setDefaults(reqMsg)
            pMod.apiMessage.setCommunity(reqMsg, "public")
            pMod.apiMessage.setPDU(reqMsg, reqPDU)

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
                if not name.startswith(('enp','wlp')):
                    continue
                ip = self.get_ip_address( name )
                if ip:
                    nic.append( (name, ip) )
        except Exception as e:
            log(f'nic_info: Exception: {e}', )
            log(traceback.format_exc())
      
        log(f'nic_info: {nic}', )
        return nic

    # noinspection PyUnusedLocal,PyUnusedLocal
    def cbRecvFun(self, tav, transportDispatcher, transportDomain, transportAddress, wholeMsg, reqPDU=None):
        hostname = None
        sysDescr = None
        macAddress = None
        while wholeMsg:
            pmod = self.pMods[tav]
            rspMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=pmod.Message())
            rspPDU = pmod.apiMessage.getPDU(rspMsg)
            rspPDURequestID = pmod.apiPDU.getRequestID(rspPDU)
            # Check for SNMP errors reported
            errorStatus = pmod.apiPDU.getErrorStatus(rspPDU)
            serialNumber = macAddress = hostname = sysDescr = None
            if not errorStatus:
                for oid, val in pmod.apiPDU.getVarBinds(rspPDU):
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
                transportDispatcher.jobFinished(1)
            else:
                log('cbRecvFun[%s:%s] errorStatus: %s' % (tav, transportAddress[0], errorStatus.prettyPrint()), )
                continue
        return wholeMsg

    def broadcast_agent_discovery(self, ):

        while not self.stopEvent.is_set():
            # get the network interfaces, these may change over time, e.g. wifi
            #
            nics = self.nic_info()
            for j, (av, reqMsg) in enumerate(self.reqMsgs.items()):
                for i, (nic, address) in enumerate(nics):
                    iface = (address, None)
                    transportDispatcher = AsyncioDispatcher()
                    transportDispatcher.registerRecvCbFun(partial(self.cbRecvFun, av))

                    # UDP/IPv4
                    udpSocketTransport = udp.UdpAsyncioTransport().openClientMode(iface=iface, allow_broadcast=True)
                    transportDispatcher.registerTransport(udp.domainName, udpSocketTransport)

                    # Pass message to dispatcher
                    transportDispatcher.sendMessage( encoder.encode(reqMsg), udp.domainName, ("255.255.255.255", 161))

                    # wait for a maximum of 10 responses or time out
                    transportDispatcher.jobStarted(1, maxNumberResponses)

                    # Dispatcher will finish as all jobs counter reaches zero
                    try:
                        transportDispatcher.runDispatcher(maxWaitForResponses)
                    except:
                        raise
                    finally:
                        pass
                    transportDispatcher.closeDispatcher()

    def run(self):

        while not self.stopEvent.is_set():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.broadcast_agent_discovery())
            except Exception as e:
                #log(f'{self.name}: Exception: {e}')
                pass
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
    threads = {}
    threads['discoveryv1'] = DiscoveryThread(name='broadcast_agent_discovery v1', av='v1',
                                   changeEvent=changeEvent, stopEvent=stopEvent, 
                                   snmpDiscoveredQueue=snmpDiscoveredQueue)

    threads['discoverv2'] = DiscoveryThread(name='broadcast_agent_discoveryv2c', av='v2c',
                                   changeEvent=changeEvent, stopEvent=stopEvent, 
                                   snmpDiscoveredQueue=snmpDiscoveredQueue)

    [v.start() for k, v in threads.items()]

    while not stopEvent.is_set():
        while not snmpDiscoveredQueue.empty():
            hostaddr, hostname, sysdescr, macAddress, serialNumber = snmpDiscoveredQueue.get()
        sleep(2)


    pass

if __name__ == '__main__':
    discoveryMain()
