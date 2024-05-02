
import sys
from time import sleep, time
import traceback
import asyncio
from threading import Thread, Event
from queue import Queue
import signal
from enum import Enum

from pysnmp.carrier.asyncio.dispatch import AsyncioDispatcher
from pysnmp.carrier.asyncio.dgram import udp
from pyasn1.codec.ber import encoder, decoder
from pysnmp.proto import api

from easysnmp.exceptions import EasySNMPTimeoutError
from easysnmp import Session


class QLSNMPStatus (Enum):
    UNKNOWN = 0
    NOTAVAILABLE = 1
    READY = 2
    BUSY = 3
    PRINTING = 4
    COVEROPEN = 5
    ERROR = 6


class SNMPThread(Thread, ):

  #def safe_str(self, p,s1,msg):
    def safe_str(self, s1):
        try:
            if '\x00' in s1:
                #log('%s: safe_str[%s]: IGNORING for null bytes' % (p, msg))
                return ''

            return str(s1)
        except UnicodeEncodeError:
            s = s1.encode('ascii', 'ignore').decode('ascii')
            print('safe_str[%s]: IGNORING: "%s"' % (msg, s), file=sys.stderr)
        return ''

    def __init__(self, changeEvent=None, stopEvent=None, hostname=None, hostaddr=None, sysdescr=None, name=None, **kwargs ):
        super(SNMPThread, self).__init__(name=name, **kwargs)
        print('[%s] starting thread' % (hostname), file=sys.stderr)
        self.changeEvent = changeEvent
        self.stopEvent = stopEvent
        self.hostname = hostname
        self.hostaddr = hostaddr
        self.sysdescr = sysdescr
        self.updateLastTime()

        # Devices are identified by MAC address or Serial Number by preference. If neither is available, use the IP address.
        # The IP address can change if the device is disconnected and reconnected to the network, and the DHCP server assigns 
        # a different IP address. The MAC address and Serial Number are fixed and unique to the device. 
        self.MACAddress = None
        self.SerialNumber = None
        self.id = None

    def updateLastTime(self):
        self.lastDiscovered = time()


# Printer SNMP Thread
# This will verify that the printer is online and responding to SNMP requests. It also gets
# the MAC address and Serial Number of the printer and current status, page count, and media type.
# Currently tested with:
#   - QL1060nw
#   - QL720w
#   - QL720nw
#
# N.b. the older QL1060nw does not support version 2c, only version 1.
#
class PrinterSNMPThread(SNMPThread, ):

    # Printer SNMP OIDs for status and info
    # We only get info once, then we get status every second
    info_printer_oids = {
                'iso.3.6.1.2.1.25.3.2.1.3.1':  'Model',       
                'iso.3.6.1.2.1.1.1.0':         'Description', 
                'iso.3.6.1.2.1.2.2.1.6.2':     'MACAddress',
                'iso.3.6.1.2.1.43.5.1.1.17.1': 'SerialNumber',
        }

    status_printer_oids = {
                "iso.3.6.1.2.1.1.3.0": "SysUpTime",
                'iso.3.6.1.4.1.11.2.4.3.1.2.0': 'Status',    
                'iso.3.6.1.2.1.43.8.2.1.12.1.1': 'Media', 
                'iso.3.6.1.2.1.43.10.2.1.4.1.1': 'PageCount',
                'iso.3.6.1.2.1.2.2.1.6.2':     'MACAddress',
                'iso.3.6.1.2.1.43.5.1.1.17.1': 'SerialNumber',
        }

    def __init__(self, printerStatusQueue=None, **kwargs ):
        self.printerStatusQueue = printerStatusQueue
        super(PrinterSNMPThread, self).__init__(**kwargs)
        print('PrinterSNMPThread: %s' % (self.hostname,), file=sys.stderr)
        self.snmpsession = Session(hostname=self.hostaddr, community='public', version=1, timeout=.2, retries=0, use_sprint_value=False)
        self.lastSeen = time()
        #self.snmpStatus = {}
        self.infoFlag = True
        #self.update({'hostaddr': self.hostaddr, 'hostname': self.hostname, 'sysdescr': self.sysdescr})

    def update(self, snmpStatus=None):
        #print('PrinterSNMPThread.update[%s:%s] sending snmpStatus: id: %s %s' % (self.hostname, self.hostaddr, self.id, snmpStatus), file=sys.stderr)
        self.printerStatusQueue.put({self.id: snmpStatus})
        self.changeEvent.set()


    def snmpStatus(self, snmpvalue):
        #print('PrinterSNMPThread.snmpStatus[%s:%s] %s' % (self.hostname, self.hostaddr, self.snmpStatus), file=sys.stderr)
        snmptests = [
                (SNMPStatus.NOTAVAILABLE, 'NOT AVAILABLE', 'Not Available'),
                (SNMPStatus.READY, 'READY', 'Ready'),
                (SNMPStatus.BUSY, 'BUSY', 'Busy'),
                (SNMPStatus.PRINTING, 'PRINTING', 'Printing'),
                (SNMPStatus.COVEROPEN, 'COVER OPEN', 'Printer Cover Open'),
                (SNMPStatus.ERROR, 'ERROR', 'Error'),
                (SNMPStatus.UNKNOWN, 'UNKNOWN', 'Unknown')
                ]
        
        for s in snmptests:
            if re.match(r'%s' % s[1], snmpvalue):
                self.snmpstatus = s[0]
                self.snmpinfo = s[2]
                break
        return self.snmpStatus


    def run(self):
        while not self.stopEvent.is_set():
            #print('PrinterSNMPThread.run: %s' % (self.hostname,), file=sys.stderr)

            oidList = self.info_printer_oids if self.infoFlag else self.status_printer_oids
            self.infoFlag = False
            oids = [oid for oid in oidList.keys()]
            #print('PrinterSNMPThread.run[%s:%s] oids: %s' % (self.hostname, self.hostaddr, oids), file=sys.stderr)
            snmpStatus = {'hostaddr': self.hostaddr, 'hostname': self.hostname}
            try:
                data = self.snmpsession.get(oids)
                #print('PrinterSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, data), file=sys.stderr)
                #s = self.safe_str(data.value).strip()
                #snmp_status[snmp_name] = s
                self.lastSeen = time()
                for d in data:
                    snmp_name = oidList[d.oid]
                    if snmp_name == 'MACAddress':
                        snmp_value = ':'.join(['%02x' % ord(c) for c in d.value])
                    else:
                        snmp_value = self.safe_str(d.value).strip()
                    #print('PrinterSNMPThread.run[%s:%s] %s: value: %s' % (self.hostname, self.hostaddr, snmp_name, snmp_value), file=sys.stderr)
                    snmpStatus[snmp_name] = snmp_value
            except EasySNMPTimeoutError as e:
                print('PrinterSNMPThread.run[%s:%s] Exception: %s exiting' % (self.hostname, self.hostaddr, e), file=sys.stderr)
                self.changeEvent.set()
                return

            except Exception as e:
                print('PrinterSNMPThread.run[%s:%s] Exception: %s continuing' % (self.hostname, self.hostaddr, e), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                continue

            if not self.id:
                self.id = snmpStatus.get('SerialNumber', None)
                if not self.id:
                    self.id = snmpStatus.get('MACAddress', None)
                if not self.id:
                    self.id = self.hostname
                #print('PrinterSNMPThread.run[%s:%s] id: %s snmpStatus: %s' % (self.hostname, self.hostaddr, self.id, snmpStatus), file=sys.stderr)

            #snmp_status['LASTSEEN'] = self.lastSeen
            self.updateLastTime()
            self.update(snmpStatus)
            #self.snmpStatus = snmp_status
            #print('PrinterSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, {k:snmp_status[k] for k in sorted(snmp_status)}), file=sys.stderr)
            #print('PrinterSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, [v for k, v in snmp_status.items()]), file=sys.stderr)
            if time() - self.lastSeen > 60:
                print('PrinterSNMPThread.run[%s:%s] timeout' % (self.hostname, self.hostaddr), file=sys.stderr)
                break
            sleep(1)
            pass

    #def status(self):
    #    return self.snmpStatus


# Impinj RFID Reader SNMP Thread
# This will verify that the Impinj RFID reader is online and responding to SNMP requests.
# It will also get the MAC address and Serial Number of the reader.
# Currently the only testing is with the older R1000, it does not support serial number.
class ImpinjSNMPThread(SNMPThread, ):

    # Impinj SNMP OIDs for status and info
    # We only get info once, then we get status every second
    info_impinj_oids = {
                #'1.3.6.1.4.1.11.2.4.3.1.2.0':'Status',      
                #'1.3.6.1.2.1.25.3.2.1.3.1':  'Model',       
                'iso.3.6.1.2.1.1.1.0':         'Description', 
                'iso.3.6.1.2.1.1.5.0':        'SysName',
                'iso.3.6.1.2.1.2.2.1.6.2':     'MACAddress',
        }

    status_impinj_oids = {
                "iso.3.6.1.2.1.1.3.0": "SysUpTime",
                'iso.3.6.1.2.1.2.2.1.6.2':     'MACAddress',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5': 'Antenna1',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5.1': 'Antenna1',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5.2': 'Antenna2',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5.3': 'Antenna3',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5.4': 'Antenna4',
        }

    def __init__(self, impinjStatusQueue=None, **kwargs ):
        self.impinjStatusQueue = impinjStatusQueue
        super(ImpinjSNMPThread, self).__init__(**kwargs)
        #print('ImpinjSNMPThread: %s address: %s' % (self.hostname, self.hostaddr), file=sys.stderr)
        self.snmpsession = Session(hostname=self.hostaddr, community='public', version=2, timeout=2, retries=2, retry_no_such=True)
        self.lastSeen = time()
        #self.snmpStatus = {}
        self.infoFlag = True
        #self.update({'hostaddr': self.hostaddr, 'hostname': self.hostname, 'sysdescr': self.sysdescr})

    def update(self, snmpStatus=None):
        print('ImpinjSNMPThread.update[%s][%s:%s] %s' % (self.id, self.hostname, self.hostaddr, snmpStatus), file=sys.stderr)
        self.impinjStatusQueue.put({self.id: snmpStatus})
        self.changeEvent.set()

    def run(self):
        while not self.stopEvent.is_set():
            #print('ImpinjSNMPThread.run: %s' % (self.hostname,), file=sys.stderr)

            oidList = self.info_impinj_oids if self.infoFlag else self.status_impinj_oids
            oids = [oid for oid in oidList.keys()]
            #print('ImpinjSNMPThread.run[%s:%s] oids: %s' % (self.hostname, self.hostaddr, oids), file=sys.stderr)
            self.infoFlag = False
            snmpStatus = {'hostaddr': self.hostaddr, 'hostname': self.hostname}
            try:
                data = self.snmpsession.get(oids)
                #print('ImpinjSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, oids), file=sys.stderr)
                #print('ImpinjSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, data), file=sys.stderr)
                #s = self.safe_str(data.value).strip()
                #snmp_status[snmp_name] = s
                self.lastSeen = time()
                for d in data:
                    snmp_name = oidList[d.oid]
                    if snmp_name == 'MACAddress':
                        snmp_value = ':'.join(['%02x' % ord(c) for c in d.value])
                    else:
                        snmp_value = self.safe_str(d.value).strip()
                    snmpStatus[snmp_name] = snmp_value
            except Exception as e:
                print('ImpinjSNMPThread.run[%s:%] Exception: %s' % (self.hostname, self.hostaddr, e), file=sys.stderr)
                print(traceback.format_exc(), file=sys.stderr)
                continue

            if not self.id:
                self.id = snmpStatus.get('MACAddress', None)
                if not self.id:
                    self.id = self.hostname
                print('ImpinjSNMPThread.run[%s:%s] id: %s snmpStatus: %s' % (self.hostname, self.hostaddr, self.id, snmpStatus), file=sys.stderr)

            #snmp_status['LASTSEEN'] = self.lastSeen
            self.updateLastTime()
            self.update(snmpStatus)
            #self.snmpStatus = snmp_status
            #print('ImpinjSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, {k:snmp_status[k] for k in sorted(snmp_status)}), file=sys.stderr)
            #print('ImpinjSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, [v for k, v in snmp_status.items()]), file=sys.stderr)
            if time() - self.lastSeen > 60:
                print('ImpinjSNMPThread.run[%s:%s] timeout' % (self.hostname, self.hostaddr), file=sys.stderr)
                break
            sleep(4)
            pass

    #def status(self):
    #    return self.snmpStatus

