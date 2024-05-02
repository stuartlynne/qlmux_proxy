
import sys
import asyncio
from threading import Thread, Event
from queue import Queue
from time import sleep, time
import signal

from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto import api

from easysnmp import Session

from .utils import log

# Broadcast manager settings
maxWaitForResponses = 4
maxNumberResponses = 10


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
class DiscoveryThread(Thread, ):

    hostname = "1.3.6.1.2.1.1.5.0"              # Hostname
    sysDescr = "1.3.6.1.2.1.1.1.0"              # System Description

    # recent devices should have MACAddress
    # older Brother printers do not have MACAddress, but have SerialNumber
    # and only support api1

    MACAddress = "1.3.6.1.2.1.2.2.1.6.2"        # MRVINREACH-MIB::ifPhysAddress.2
    SerialNumber = "1.3.6.1.2.1.43.5.1.1.17.1"  # Printer-MIB::prtGeneralSerialNumber.1
    #Model = "1.3.6.1.2.1.25.3.2.1.3.1",        # Brother Model, does not work with broadcast
    #Model = "1.3.6.1.2.1.2.2.1.2.1"
    ap1_oids = [ SerialNumber, hostname, sysDescr, ]
    ap2c_oids = [ SerialNumber, hostname, sysDescr, MACAddress, ] 

            #MACAddress,
        

            #"1.3.6.1.2.1.1.1.0",        # System Description
            #"1.3.6.1.2.1.1.5.0",         # Hostname
            #"1.3.6.1.2.1.1.3.0"        # System Uptime
            #"1.3.6.1.2.1.25.3.2.1.3.1",                # Printer Name
            #"1.3.6.1.2.1.25.3.2.1.3.1",                 # Brother Model
            #"1.3.6.1.2.1.2.2.1.6.1",                   # Brother uses this in br-admin   
            #"1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.1.0",    # Brother Serial number
            #"1.3.6.1.4.1.11.2.4.3.1.2.0",               # Brother Status
            #"1.3.6.1.2.1.43.8.2.1.12.1.1",              # Brother Media

            #"1.3.6.1.4.1.22695.1.1.1.2.1.1.5.1", # RFID reader antennas
            #"1.3.6.1.4.1.22695.1.1.1.2.1.1.5.2", # RFID reader antennas
            #"1.3.6.1.4.1.22695.1.1.1.2.1.1.5.3", # RFID reader antennas
            #"1.3.6.1.4.1.22695.1.1.1.2.1.1.5.4", # RFID reader antennas
            #"1.3.6.1.4.1.22695.1.1.1.2.1",       # RFID reader antennas
            
            #"1.3.6.1.4.1.25882.2.1.1",             # System Uptime

    def __init__(self, api_version=None, name=None, snmpDiscoveredQueue=None, stopEvent=None, changeEvent=None, **kwargs):
        log('Discovery: snmpDiscoveredQueue: %s' % (snmpDiscoveredQueue), )

        self.oids = self.ap2c_oids if api_version == api.protoVersion2c else self.ap1_oids

        log('Discovery: oids: %s' % (self.oids), )
        self.snmpDiscoveredQueue = snmpDiscoveredQueue
        if not self.snmpDiscoveredQueue:
            raise Exception('DiscoveryThread: snmpDiscoveredQueue is None')
        super(DiscoveryThread, self).__init__(name=name, kwargs=kwargs)
        log('[%s] starting thread' % self.name, )
        self.name = name
        self.api_version = api_version
        self.stopEvent = stopEvent
        self.changeEvent = changeEvent

    def broadcast_agent_discovery(self, api_version=api.protoVersion2c, community='public', oids=()):

        av = '2c' if api_version == api.protoVersion2c else '1'

        pMod = api.protoModules[api_version]

        # Build PDU
        reqPDU = pMod.GetRequestPDU()
        pMod.apiPDU.setDefaults(reqPDU)

        oidList = [(oid, pMod.Null("")) for oid in oids]
                

        pMod.apiPDU.setVarBinds(
            reqPDU, 
            oidList,
        )

        # Build message
        reqMsg = pMod.Message()
        pMod.apiMessage.setDefaults(reqMsg)
        pMod.apiMessage.setCommunity(reqMsg, "public")
        pMod.apiMessage.setPDU(reqMsg, reqPDU)


        # noinspection PyUnusedLocal,PyUnusedLocal
        def cbRecvFun( transportDispatcher, transportDomain, transportAddress, wholeMsg, reqPDU=reqPDU):
            hostname = None
            sysDescr = None
            macAddress = None
            while wholeMsg:
                rspMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=pMod.Message())
                rspPDU = pMod.apiMessage.getPDU(rspMsg)
                #log('transportAddress: %s' % (transportAddress[0]))
                # Match response to request
                if pMod.apiPDU.getRequestID(reqPDU) == pMod.apiPDU.getRequestID(rspPDU):
                    # Check for SNMP errors reported
                    errorStatus = pMod.apiPDU.getErrorStatus(rspPDU)
                    serialNumber = macAddress = hostname = sysDescr = None
                    if not errorStatus:
                        for oid, val in pMod.apiPDU.getVarBinds(rspPDU):
                            #log('oid: %s' % (oid,), )
                            match str(oid):
                                case self.SerialNumber:
                                    #log(f'cbRecvFun: {transportAddress[0]}: SERIALNUMBER {val}', )
                                    serialNumber = val
                                    #log(f'cbRecvFun: {transportAddress[0]}: SERIALNUMBER {serialNumber}', )
                                case self.MACAddress:
                                    macAddress = val.prettyPrint()
                                    #log(f'cbRecvFun: {transportAddress[0]}: MACADDRESS {macAddress}', )
                                case self.hostname:
                                    hostname = val.prettyPrint()
                                    #log(f'cbRecvFun: {transportAddress[0]}: HOSTNAME {hostname}', )
                                case self.sysDescr:
                                    sysDescr = val.prettyPrint()
                                    #log(f'cbRecvFun: {transportAddress[0]}: SYSDESCR {sysDescr}', )
                                case _:
                                    log(f'cbRecvFun: oid unknown: %s' % oid, )

                            #log(f"{transportAddress[0]}: {oid.prettyPrint()} = {val.prettyPrint()}", )
                    #else:
                    #    print(errorStatus.prettyPrint())
                    if hostname or sysDescr:
                        #log('cbRecvFun[%s] hostname: %s macAddress: %s serialNumber: %s sysDescr: %s' % (transportAddress[0], hostname, macAddress, serialNumber, sysDescr, ), )
                        self.snmpDiscoveredQueue.put((transportAddress[0], hostname, sysDescr, macAddress, serialNumber, ))
                        #log(f'{transportAddress[0]}: {hostname} {sysDescr}')
                        self.changeEvent.set()
                    transportDispatcher.jobFinished(1)
            return wholeMsg


        while not self.stopEvent.is_set():
            transportDispatcher = AsyncioDispatcher()

            transportDispatcher.registerRecvCbFun(cbRecvFun)

            # UDP/IPv4
            udpSocketTransport = udp.UdpAsyncioTransport().openClientMode(allow_broadcast=True)
            transportDispatcher.registerTransport(udp.domainName, udpSocketTransport)

            # Pass message to dispatcher
            transportDispatcher.sendMessage( encoder.encode(reqMsg), udp.domainName, ("255.255.255.255", 161))

            # wait for a maximum of 10 responses or time out
            transportDispatcher.jobStarted(1, maxNumberResponses)

            # Dispatcher will finish as all jobs counter reaches zero
            try:
                transportDispatcher.runDispatcher(4)
            except:
                raise
            finally:
                pass
            transportDispatcher.closeDispatcher()

    def run(self):
        log('[%s] starting run loop' % self.name, )
        while not self.stopEvent.is_set():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            log('%s: loop run until complete' % (self.name,), )
            try:
                loop.run_until_complete(self.broadcast_agent_discovery(
                    api_version=self.api_version,
                    oids=self.oids))
                #loop.run_forever(broadcast_agent_discovery(api_version=self.api_version ))
            except Exception as e:
                #log(f'{self.name}: Exception: {e}')
                pass
            log('%s: loop finished' % (self.name), )
            loop.stop()
            loop.close()
            sleep(1)
            log('%s: loop closed' % (self.name,), )
            break


