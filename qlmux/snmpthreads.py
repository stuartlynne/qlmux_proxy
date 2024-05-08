
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
from .utils import log

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
            log('safe_str[%s]: IGNORING: "%s"' % (msg, s), )
        return ''

    def __init__(self, changeEvent=None, stopEvent=None, hostname=None, hostaddr=None, sysdescr=None, name=None, **kwargs ):
        super(SNMPThread, self).__init__(name=name, **kwargs)
        log('[%s] starting thread' % (hostname), )
        self.changeEvent = changeEvent
        self.stopEvent = stopEvent
        self.hostname = hostname
        self.hostaddr = hostaddr
        self.sysdescr = sysdescr
        self.updateLastTime()

        # Devices are identified by MAC address or Serial Number by preference. If neither is available, use the IP address.
        # The IP address can change if the device is disconnected and reconnected to the network, and the DHCP server assigns 
        # a different IP address. The MAC address and Serial Number are fixed and unique to the device. 
        self.serialNumber = None
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
                '.1.3.6.1.2.1.25.3.2.1.3.1':  'sysName',       
                '.1.3.6.1.2.1.1.1.0':         'sysDescr', 
                '.1.3.6.1.2.1.2.2.1.6.2':     'ifPhyAddress',
                '.1.3.6.1.2.1.43.5.1.1.17.1': 'serialNumber',
        }

    status_printer_oids = {
                ".1.3.6.1.2.1.1.3.0": "SysUpTime",
                '.1.3.6.1.4.1.11.2.4.3.1.2.0': 'Status',    
                '.1.3.6.1.2.1.43.8.2.1.12.1.1': 'Media', 
                '.1.3.6.1.2.1.43.10.2.1.4.1.1': 'PageCount',
                '.1.3.6.1.2.1.2.2.1.6.2':     'ifPhyAddress',
                '.1.3.6.1.2.1.43.5.1.1.17.1': 'serialNumber',
        }

    def __init__(self, printerStatusQueue=None, **kwargs ):
        self.printerStatusQueue = printerStatusQueue
        super(PrinterSNMPThread, self).__init__(**kwargs)
        log('PrinterSNMPThread: %s' % (self.hostname,), )
        self.snmpsession = Session(hostname=self.hostaddr, community='public', version=1, timeout=.2, retries=0, use_sprint_value=False,
                                   use_numeric=False, use_long_names=True )
        self.lastSeen = time()
        #self.snmpStatus = {}
        self.infoFlag = True
        #self.update({'hostaddr': self.hostaddr, 'hostname': self.hostname, 'sysdescr': self.sysdescr})

    def update(self, snmpStatus=None):
        #log('PrinterSNMPThread.update[%s:%s] sending snmpStatus: id: %s %s' % (self.hostname, self.hostaddr, self.id, snmpStatus), )
        self.printerStatusQueue.put({self.id: snmpStatus})
        self.changeEvent.set()


    def snmpStatus(self, snmpvalue):
        #log('PrinterSNMPThread.snmpStatus[%s:%s] %s' % (self.hostname, self.hostaddr, self.snmpStatus), )
        snmptests = [
                (QLSNMPStatus.NOTAVAILABLE, 'NOT AVAILABLE', 'Not Available'),
                (QLSNMPStatus.READY, 'READY', 'Ready'),
                (QLSNMPStatus.BUSY, 'BUSY', 'Busy'),
                (QLSNMPStatus.PRINTING, 'PRINTING', 'Printing'),
                (QLSNMPStatus.COVEROPEN, 'COVER OPEN', 'Printer Cover Open'),
                (QLSNMPStatus.ERROR, 'ERROR', 'Error'),
                (QLSNMPStatus.UNKNOWN, 'UNKNOWN', 'Unknown')
                ]
        
        for s in snmptests:
            if re.match(r'%s' % s[1], snmpvalue):
                self.snmpstatus = s[0]
                self.snmpinfo = s[2]
                break
        return self.snmpStatus


    def run(self):
        while not self.stopEvent.is_set():
            #log('PrinterSNMPThread.run: %s' % (self.hostname,), )

            oidList = self.info_printer_oids if self.infoFlag else self.status_printer_oids
            self.infoFlag = False
            oids = [oid for oid in oidList.keys()]
            #log('PrinterSNMPThread.run[%s:%s] oids: %s' % (self.hostname, self.hostaddr, oids), )
            snmpStatus = {'hostaddr': self.hostaddr, 'hostname': self.hostname}
            try:
                data = self.snmpsession.get(oids)
                #log('PrinterSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, data), )
                #s = self.safe_str(data.value).strip()
                #snmp_status[snmp_name] = s
                self.lastSeen = time()
                for d in data:
                    log('PrinterSNMPThread.run[%s:%s] %s: %s' % (self.hostname, self.hostaddr, d.oid, d.value), )
                    try:
                        snmp_name = oidList[d.oid]
                        if snmp_name == 'ifPhyAddress':
                            snmp_value = ':'.join(['%02x' % ord(c) for c in d.value])
                        else:
                            snmp_value = self.safe_str(d.value).strip()
                        #log('PrinterSNMPThread.run[%s:%s] %s: value: %s' % (self.hostname, self.hostaddr, snmp_name, snmp_value), )
                        snmpStatus[snmp_name] = snmp_value
                    except Exception as e:
                        log('PrinterSNMPThread.run[%s:%s] Exception: %s' % (self.hostname, self.hostaddr, e), )
            except EasySNMPTimeoutError as e:
                snmpStatus['Status'] = 'NOT AVAILABLE'
                self.update(snmpStatus)
                log('PrinterSNMPThread.run[%s:%s] Exception: %s exiting' % (self.hostname, self.hostaddr, e), )
                self.changeEvent.set()
                return

            except Exception as e:
                log('PrinterSNMPThread.run[%s:%s] Exception: %s continuing' % (self.hostname, self.hostaddr, e), )
                log(traceback.format_exc(), )
                continue

            if not self.id:
                self.id = snmpStatus.get('serialNumber', None)
                if not self.id:
                    self.id = snmpStatus.get('ifPhyAddress', None)
                if not self.id:
                    self.id = self.hostname
                log('PrinterSNMPThread.run[%s:%s] id: %s snmpStatus: %s' % (self.hostname, self.hostaddr, self.id, snmpStatus), )

            #snmp_status['LASTSEEN'] = self.lastSeen
            self.updateLastTime()
            self.update(snmpStatus)
            #self.snmpStatus = snmp_status
            #log('PrinterSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, {k:snmp_status[k] for k in sorted(snmp_status)}), )
            #log('PrinterSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, [v for k, v in snmp_status.items()]), )
            if time() - self.lastSeen > 60:
                log('PrinterSNMPThread.run[%s:%s] timeout' % (self.hostname, self.hostaddr), )
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
                '.1.3.6.1.2.1.1.1.0':         'Description', 
                '.1.3.6.1.2.1.1.5.0':        'SysName',
                '.1.3.6.1.2.1.2.2.1.6.2':     'ifPhyAddress',
        }

    status_impinj_oids = {
                ".1.3.6.1.2.1.1.3.0": "SysUpTime",
                '.1.3.6.1.2.1.2.2.1.6.2':     'ifPhyAddress',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5': 'Antenna1',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5.1': 'Antenna1',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5.2': 'Antenna2',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5.3': 'Antenna3',
                #'iso.3.6.1.4.1.22695.1.1.1.2.1.1.5.4': 'Antenna4',
        }

    def __init__(self, impinjStatusQueue=None, **kwargs ):
        self.impinjStatusQueue = impinjStatusQueue
        super(ImpinjSNMPThread, self).__init__(**kwargs)
        #log('ImpinjSNMPThread: %s address: %s' % (self.hostname, self.hostaddr), )
        self.snmpsession = Session(hostname=self.hostaddr, community='public', version=2, timeout=2, retries=2, retry_no_such=True,
                                   use_numeric=False, use_long_names=True)
        self.lastSeen = time()
        #self.snmpStatus = {}
        self.infoFlag = True
        #self.update({'hostaddr': self.hostaddr, 'hostname': self.hostname, 'sysdescr': self.sysdescr})

    def update(self, snmpStatus=None):
        #log('ImpinjSNMPThread.update[%s][%s:%s] %s' % (self.id, self.hostname, self.hostaddr, snmpStatus), )
        self.impinjStatusQueue.put({self.id: snmpStatus})
        self.changeEvent.set()

    def run(self):
        while not self.stopEvent.is_set():
            #log('ImpinjSNMPThread.run: %s' % (self.hostname,), )

            oidList = self.info_impinj_oids if self.infoFlag else self.status_impinj_oids
            oids = [oid for oid in oidList.keys()]
            #log('ImpinjSNMPThread.run[%s:%s] oids: %s' % (self.hostname, self.hostaddr, oids), )
            self.infoFlag = False
            snmpStatus = {'hostaddr': self.hostaddr, 'hostname': self.hostname}
            try:
                data = self.snmpsession.get(oids)
                #log('ImpinjSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, oids), )
                #log('ImpinjSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, data), )
                #s = self.safe_str(data.value).strip()
                #snmp_status[snmp_name] = s
                self.lastSeen = time()
                for d in data:
                    try:
                        snmp_name = oidList[d.oid]
                        if snmp_name == 'ifPhyAddress':
                            snmp_value = ':'.join(['%02x' % ord(c) for c in d.value])
                        else:
                            snmp_value = self.safe_str(d.value).strip()
                        snmpStatus[snmp_name] = snmp_value
                    except Exception as e:
                        log('ImpinjSNMPThread.run[%s:%s] Exception: %s' % (self.hostname, self.hostaddr, e), )
            except Exception as e:
                log('ImpinjSNMPThread.run[%s:%s] Exception: %s' % (self.hostname, self.hostaddr, e), )
                log(traceback.format_exc(), )
                continue

            if not self.id:
                self.id = snmpStatus.get('ifPhyAddress', None)
                if not self.id:
                    self.id = self.hostname
                #log('ImpinjSNMPThread.run[%s:%s] id: %s snmpStatus: %s' % (self.hostname, self.hostaddr, self.id, snmpStatus), )

            #snmp_status['LASTSEEN'] = self.lastSeen
            self.updateLastTime()
            self.update(snmpStatus)
            #self.snmpStatus = snmp_status
            #log('ImpinjSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, {k:snmp_status[k] for k in sorted(snmp_status)}), )
            #log('ImpinjSNMPThread.run[%s:%s] %s' % (self.hostname, self.hostaddr, [v for k, v in snmp_status.items()]), )
            if time() - self.lastSeen > 60:
                log('ImpinjSNMPThread.run[%s:%s] timeout' % (self.hostname, self.hostaddr), )
                break
            sleep(4)
            pass

    #def status(self):
    #    return self.snmpStatus

