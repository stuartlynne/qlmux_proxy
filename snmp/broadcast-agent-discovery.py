
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

# Broadcast manager settings
maxWaitForResponses = 4
maxNumberResponses = 10


  
class DiscoveryThread(Thread, ):

    hostname = "1.3.6.1.2.1.1.5.0"         # Hostname
    sysDescr = "1.3.6.1.2.1.1.1.0"        # System Description
    oids = (
            hostname, 
            sysDescr,
            "1.3.6.1.2.1.1.1.0",        # System Description
            "1.3.6.1.2.1.1.5.0",         # Hostname
            #"1.3.6.1.2.1.1.3.0"        # System Uptime
            #"1.3.6.1.2.1.25.3.2.1.3.1",                # Printer Name
            #"1.3.6.1.2.1.2.2.1.6.1",                   # Brother uses this in br-admin   
            #"1.3.6.1.4.1.2435.2.3.9.4.2.1.5.5.1.0",    # Brother Serial number
            #"1.3.6.1.4.1.11.2.4.3.1.2.0",               # Brother Status
            #"1.3.6.1.2.1.43.8.2.1.12.1.1",              # Brother Media
            #"1.3.6.1.2.1.25.3.2.1.3.1",                 # Brother Model

            #"1.3.6.1.4.1.22695.1.1.1.2.1.1.5.1", # RFID reader antennas
            #"1.3.6.1.4.1.22695.1.1.1.2.1.1.5.2", # RFID reader antennas
            #"1.3.6.1.4.1.22695.1.1.1.2.1.1.5.3", # RFID reader antennas
            #"1.3.6.1.4.1.22695.1.1.1.2.1.1.5.4", # RFID reader antennas
            #"1.3.6.1.4.1.22695.1.1.1.2.1",       # RFID reader antennas
            
            #"1.3.6.1.4.1.25882.2.1.1",             # System Uptime
        )

    def __init__(self, api_version=None, name=None, discoveryQueue=None, stopEvent=None, changeEvent=None, **kwargs):
        super(DiscoveryThread, self).__init__(name=name, kwargs=kwargs)
        print('[%s] starting thread' % self.name)
        self.name = name
        self.api_version = api_version
        self.stopEvent = stopEvent
        self.changeEvent = changeEvent
        self.discoveryQueue = discoveryQueue

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
            while wholeMsg:
                rspMsg, wholeMsg = decoder.decode(wholeMsg, asn1Spec=pMod.Message())
                rspPDU = pMod.apiMessage.getPDU(rspMsg)
                #print('transportAddress: %s' % (transportAddress[0]))
                # Match response to request
                if pMod.apiPDU.getRequestID(reqPDU) == pMod.apiPDU.getRequestID(rspPDU):
                    # Check for SNMP errors reported
                    errorStatus = pMod.apiPDU.getErrorStatus(rspPDU)
                    if not errorStatus:
                        for oid, val in pMod.apiPDU.getVarBinds(rspPDU):
                            #print('oid: %s' % (oid,), file=sys.stderr)
                            match str(oid):
                                case self.hostname:
                                    hostname = val.prettyPrint()
                                    #print(f'{transportAddress[0]}: HOSTNAME {hostname}', file=sys.stderr)
                                case self.sysDescr:
                                    sysDescr = val.prettyPrint()
                                    #print(f'{transportAddress[0]}: SYSDESCR {sysDescr}', file=sys.stderr)
                            #print(f"{transportAddress[0]}: {oid.prettyPrint()} = {val.prettyPrint()}", file=sys.stderr)
                    #else:
                    #    print(errorStatus.prettyPrint())
                    if hostname or sysDescr:
                        self.discoveryQueue.put((transportAddress[0], hostname, sysDescr))
                        #print(f'{transportAddress[0]}: {hostname} {sysDescr}')
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
        print('[%s] starting run loop' % self.name)
        while not self.stopEvent.is_set():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            print('%s: loop run until complete' % (self.name,))
            try:
                loop.run_until_complete(self.broadcast_agent_discovery(
                    api_version=self.api_version,
                    oids=self.oids))
                #loop.run_forever(broadcast_agent_discovery(api_version=self.api_version ))
            except Exception as e:
                #print(f'{self.name}: Exception: {e}')
                pass
            print('%s: loop finished' % (self.name,))
            loop.close()
            sleep(1)
            print('%s: loop closed' % (self.name,))
            break

class SNMPThread(Thread, ):

  #def safe_str(self, p,s1,msg):
    def safe_str(self, s1):
        s = ''
        try:
            return str(s1)
        except UnicodeEncodeError:
            s = s1.encode('ascii', 'ignore').decode('ascii')
            print('safe_str[%s]: IGNORING: "%s"' % (msg, s))
        return ''

    def __init__(self, changeEvent=None, stopEvent=None, hostname=None, hostaddr=None, sysdescr=None, name=None, **kwargs ):
        super(SNMPThread, self).__init__(name=name, **kwargs)
        print('[%s] starting thread' % (hostname), file=sys.stderr)
        self.changeEvent = changeEvent
        self.changeEvent.clear()
        self.stopEvent = stopEvent
        self.hostname = hostname
        self.hostaddr = hostaddr
        self.sysdescr = sysdescr
        self.update()

    def update(self):
        self.lastDiscovered = time()


class PrinterSNMPThread(SNMPThread, ):

    printer_oids = (
                ('STATUS', 'iso.3.6.1.4.1.11.2.4.3.1.2.0', ),
                ('MEDIA', 'iso.3.6.1.2.1.43.8.2.1.12.1.1',),
                ('MODEL', 'iso.3.6.1.2.1.25.3.2.1.3.1',),
        )

    def __init__(self, **kwargs ):
        super(PrinterSNMPThread, self).__init__(**kwargs)
        print('PrinterSNMPThread: %s' % (self.hostname,), file=sys.stderr)
        self.snmpsession = Session(hostname=self.hostaddr, community='public', version=1, timeout=.2, retries=0)
        self.lastSeen = time()

    def run(self):
        while not self.stopEvent.is_set():
            #print('PrinterSNMPThread.run: %s' % (self.hostname,), file=sys.stderr)
            snmp_status = {'MODEL': '', 'MEDIA': '', 'STATUS': ''}

            for snmp_name, oid in self.printer_oids:
                try:
                    data = self.snmpsession.get(oid)
                    s = self.safe_str(data.value).strip()
                    snmp_status[snmp_name] = s
                    self.lastSeen = time()
                except Exception as e:
                    print('PrinterSNMPThread.run[%s:%s] Exception: %s' % (self.hostname, self.hostaddr, e), file=sys.stderr)
                    continue

            #print('PrinterSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, {k:snmp_status[k] for k in sorted(snmp_status)}), file=sys.stderr)
            print('PrinterSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, [v for k, v in snmp_status.items()]), file=sys.stderr)
            if time() - self.lastSeen > 60:
                print('PrinterSNMPThread.run[%s:%s] timeout' % (self.hostname, self.hostaddr), file=sys.stderr)
                break
            sleep(4)
            pass


def main(argv):

    sigintEvent = Event()
    sigintEvent.clear()

    stopEvent = Event()
    stopEvent.clear()

    changeEvent = Event()
    changeEvent.clear()

    printers = {}
    impinjs = {}

    def sigintHandler(signal, frame):
        print('SIGINT received %s' % (signal,), file=sys.stderr)
        sigintEvent.set()
        changeEvent.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    discoveryQueue = Queue()

    threads = []
    threads.append(DiscoveryThread(name='broadcast_agent_discovery v1', api_version=api.protoVersion1, 
                                   changeEvent=changeEvent, stopEvent=stopEvent, discoveryQueue=discoveryQueue))
    threads.append(DiscoveryThread(name='broadcast_agent_discoveryv2c', api_version=api.protoVersion2c, 
                                   changeEvent=changeEvent, stopEvent=stopEvent, discoveryQueue=discoveryQueue))

    [t.start() for t in threads]

    while changeEvent.wait():
        changeEvent.clear()
        if sigintEvent.is_set():
            stopEvent.set()
            break
        while not discoveryQueue.empty():
            hostaddr, hostname, sysdescr = discoveryQueue.get()
            #print('discoveryQueue get: %s' % (discoveryQueue.get(),), file=sys.stderr)
            match sysdescr:
                case x if 'Impinj' in x:
                    print(f'Impinj: {hostaddr}: {hostname} {sysdescr}')

                case x if 'Brother' in x:
                    #print(f'Brother: {hostaddr}: {hostname} {sysdescr}')
                    if hostaddr not in printers:
                        printers[hostaddr] = PrinterSNMPThread(
                            hostname=hostname, hostaddr=hostaddr, sysdescr=sysdescr, changeEvent=changeEvent, stopEvent=stopEvent)
                        printers[hostaddr].start()
                    else:
                        printers[hostaddr].update()
        # look for timed out printers
        for k, v in printers.items():
            if not v.is_alive():
                del printers[k]


    print('stopping stopEvent: %s' % (stopEvent.is_set()), file=sys.stderr)

    for k, v in printers.items():
        if v.is_alive():
            v.join()
    #[t.join() for t in printers.values if t.is_alive()]
    [t.join() for t in threads if t.is_alive()]
    print('exiting')


if __name__ == '__main__':
    
    main(sys.argv[1:])

