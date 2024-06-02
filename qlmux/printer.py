# -*- coding: utf-8 -*-
# vim: syntax=python expandtab

import sys
import itertools
import datetime
#from Queue import Queue, Empty
from enum import Enum
#from easysnmp import snmp_get, snmp_set, snmp_walk
from easysnmp import Session
import re
import select
import socket
from threading import Thread as Process
from time import time, sleep
import traceback

from .utils import *

from .snmp import SNMPStatus


getTimeNow = datetime.datetime.now

def safe_str(p,s1,msg):
    try:
        if '\x00' in s1:
            log('%s: safe_str[%s]: IGNORING for null bytes' % (p, msg))
            return ''

        return str(s1)
        #print('safe_str[%s]: OK: "%s"' % (msg, s))

    except UnicodeEncodeError:
        s = s1.encode('ascii', 'ignore').decode('ascii')
        log('%s: safe_str[%s]: IGNORING: "%s"' % (p, msg, s))

    except Exception as e:
        log('updatestatus: exception: %s' % (e))
        log(traceback.format_exc(), )
        self.media = ''
    return ''





class PrinterStatus (Enum):
    UNKNOWN = 0
    NOTAVAILABLE = 1
    OK = 2
    PRINTING = 3
    def __str__(self):
        return self.name

class PrinterQueue (Enum):
    CENTER = 0
    LEFT = 1
    RIGHT = 2
    DISABLED = 3
    def __str__(self):
        return self.name


class Job( object ):
    def __init__(self, pool, data):
        self.pool = pool
        self.data = data

    def __repr__(self):
        return "\nJob[%s] %s " % ( self.pool, len(self.data))


#
# Printer
# Destinations for data.
#
#
class Printer( object ):

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.hostaddr = kwargs.get('hostaddr', '')
        self.hostname = kwargs.get('hostname', '')
        self.sysdescr = kwargs.get('sysDescr', '')
        self.macaddress = kwargs.get('ifPhyAddress', '')
        self.serialnumber = kwargs.get('serialNumber', '')
        self.model = kwargs.get('sysName', '')
        self.snmpstatus = SNMPStatus.UNKNOWN
        self.snmpvalue = ''
        self.snmpinfo = ''

        self.status = self.media = self.size = None

        self.fd = None
        self.queue = PrinterQueue.CENTER
        self.printjobs = []
        self.currentjob = None
        self.senddata = None
        self.sending = False
        self.jobsFinished = 0
        self.jobsFailed = 0

        self.lastUsed = self.lastSeen = time()



        log('Printer:__init__[%s] name: %s hostname: %s model: %s sysdescr: %s %s %s %s' % (
            self.serialnumber, self.hostname, self.hostname, self.model, self.sysdescr, self.macaddress, self.serialnumber, self.model))
        self.snmpsession = Session(hostname=self.hostaddr, community='public', version=1, timeout=.2, retries=0)

    def setQueue(self, queue):
        log('Printer:setQueue[%s] %s %s' % (self.serialnumber, self.hostname, queue.name))
        self.queue = queue

    def stats(self):
        return (self.jobsFinished, self.jobsFailed)

    def check(self, queue=None, size=None):
        if self.size != size:
            return None
        if self.queue != queue:
            return None
        if self.snmpstatus != SNMPStatus.READY:
            return None
        return self.lastUsed

    def used(self):
        self.lastUsed = time()
    def seen(self):
        self.lastSeen = time()

    def __str__(self):
        return "Printer[%s] %s %s %s %s %s %d %s" % (
                self.serialnumber, self.queue.name, self.hostname, self.model, self.snmpstatus, self.size, self.jobsFinished, 
                datetime.datetime.utcfromtimestamp(self.lastUsed).strftime('%H:%M:%S.%f')[0:-3],)

    # updatestatus
    # This is called from the SNMP process to update the printer status using SNMP
    #
    snmptests = [ (SNMPStatus.NOTAVAILABLE, 'NOT AVAILABLE', 'Not Available'),
            (SNMPStatus.READY, 'READY', 'Ready'),
            (SNMPStatus.BUSY, 'BUSY', 'Busy'),
            (SNMPStatus.PRINTING, 'PRINTING', 'Printing'),
            (SNMPStatus.COVEROPEN, 'COVER OPEN', 'Printer Cover Open'),
            (SNMPStatus.ERROR, 'ERROR', 'Error'),
            (SNMPStatus.UNKNOWN, 'UNKNOWN', 'Unknown')
            ]

    def update(self, **kwargs):

        #log('Printer:update[%s]: model: %s' % (self.hostname, self.model))
        #log('Printer:update[%s]: %s' % (self.hostname, kwargs))
        status = kwargs.get('Status', None)
        media = kwargs.get('Media', None)
        #self.model = kwargs.get('sysName', 'UNKNOWN MODEL')

        if status: 
            if self.status != status:
                log('[%s] %s Changed status: %s' % (self.serialnumber, self.hostname, self.status))
                self.snmpstatus = SNMPStatus.UNKNOWN
                self.snmpinfo = 'Unknown'
                for s in self.snmptests:
                    try:
                        if s[1] in status:
                            self.snmpstatus = s[0]
                            self.snmpinfo = s[2]
                            break
                    except Exception as e:
                        log('updatestatus[%s] %s exception: %s' % (self.serialnumber, self.hostname, e))
                        log(traceback.format_exc(), )
                        self.snmpstatus = SNMPStatus.UNKNOWN
                        #log('updatestatus[%s]: s: %s ZZZZ' % (self.hostname, s))
                log('Printer.update[%s] %s Changed status: %s --> %s' % (self.serialnumber, self.hostname, self.status, status))
                self.status = status
        #else:
        #    log('Printer.update[%s] %s status: %s None ZZZZ' % (self.serialnumber, self.hostname, self.status))

        if media:
            if self.media != media:
                if not media:
                    size = None
                elif media.startswith('62mm'):
                    size = '62mm'
                elif media.startswith('102mm'):
                    size = '102mm'
                else:
                    size = 'unknown'

                log('Printer.update[%s] %s Changed media: %s --> %s' % (self.serialnumber, self.hostname, self.media, media, ))
                self.media = media
                #log('Printer.update[%s] check size: %s --> %s' % (self.hostname, self.size, size, ))
                if self.size != size:
                    log('Printer.update[%s] %s Changed size: %s --> %s' % (self.serialnumber, self.hostname, self.size, size, ))
                    self.size = size
        #else:
        #    log('Printer.update[%s] %s media: %s None ZZZZ' % (self.serialnumber, self.hostname, self.media))



    # add a print job to the print jobs queue
    #
    def add(self, pool, data):
        self.printjobs.append(Job(pool, data))
        return

    # check if there are jobs queued to this printer and we are currently active
    #
    def checkforjobs(self):
        if len(self.printjobs) == 0:
            #log('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s NO JOBS' % (self.hostname, self.status, self.snmpstatus, len(self.printjobs)))
            #log('Printer:checkforjobs[%s] snmp: %s jobs: %s NO JOBS' % (self.hostname, self.snmpstatus, len(self.printjobs)))
            return False
        if self.snmpstatus != SNMPStatus.READY:
            log('[%s] %s snmp: %s jobs: %s SNMP NOT READY' % (self.serialnumber, self.hostname, self.snmpstatus, len(self.printjobs)))
            return False

        if self.sending:
            log('[%s] %s snmp: %s jobs: %s Already Sending' % (self.serialnumber, self.hostname, self.snmpstatus, len(self.printjobs)))
            return False

        log('[%s] %s snmp: %s jobs: %s HAVE JOBS' % (self.serialnumber, self.hostname, self.snmpstatus, len(self.printjobs)))

        # get current job and make a copy for working with
        self.currentjob = self.printjobs.pop(0)
        log('Printer:checkforjobs[%s] job: %s' % (self.hostname, self.currentjob))
        #self.senddata = list(self.currentjob.data)
        #print('Printer:checkforjobs[%s] data: %s' % (self.hostname, self.senddata))
        self.sending = True
        self.lastUsed = time()

        # XXX if True then we are faking the sending of data with no attempt
        #if False:
        #    log('[%s] %s FAKE sending' % (self.serialnumber, self.hostname))
        #    self.sending = False
        #    self.finished(True)
        #    return False

        return True

    def getJobData(self):
        return list(self.currentjob.data)

    # finished
    # Called when the print job has been finished (sent to printer). The flag is set to True for
    # success and False for possible failure.
    #
    def finished(self, flag):
        self.sending = False
        log('[%s] %s finished' % (self.serialnumber, self.hostname))
        job = self.currentjob
        self.currentjob = None
        #print('Printer:finished: currentjob: %s' % (job))
        pool = job.pool
        #print('Printer:finished: pool: %s' % (pool))

        # if there was a possible failure to deliver the print job, requeue to send again.
        #
        if not flag:
            pool.recv(job.data)
            self.jobsFailed += 1
        else:
            self.jobsFinished += 1

    def __repr__(self):
        return "Printer[%s] model: %s snmpstatus: %s snmpmedia: %s printjobs: %d\n" % (
                self.hostname, self.model, self.snmpstatus, self.media, len(self.printjobs))
