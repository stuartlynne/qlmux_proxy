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
from time import sleep
from .utils import *

from .snmp import SNMPStatus


getTimeNow = datetime.datetime.now

def safe_str(p,s1,msg):
    s = ''
    try:
        return str(s1)
        #print('safe_str[%s]: OK: "%s"' % (msg, s))

    except UnicodeEncodeError:
        s = s1.encode('ascii', 'ignore').decode('ascii')
        log('%s: safe_str[%s]: IGNORING: "%s"' % (p, msg, s))
    return ''





class PrinterStatus (Enum):
    UNKNOWN = 0
    NOTAVAILABLE = 1
    OK = 2
    PRINTING = 3



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

    def __init__(self, name, hostname, sysdescr, macaddress, serialnumber, testport, model, size):
        self.name = name
        self.hostname = hostname
        self.sysdescr = sysdescr
        self.macaddress = macaddress
        self.serialnumber = serialnumber
        self.testport = testport
        self.model = model
        self.size = size
        self.snmpstatus = SNMPStatus.UNKNOWN
        self.snmpvalue = ''
        self.snmpinfo = ''
        self.snmpmedia = 'NO LABELS'
        self.snmpmodel = 'UNKNOWN MODEL'
        self.fd = None
        self.pool = None
        self.printjobs = []
        self.currentjob = None
        self.senddata = None
        self.sending = False
        self.jobsFinished = 0
        self.errors = 0

        log('Printer:__init__: name: %s hostname: %s sysdescr: %s %s %s %s %s' % (self.name, self.hostname, self.sysdescr, self.macaddress, self.serialnumber, self.testport, self.model))

        self.snmpsession = Session(hostname=hostname, community='public', version=1, timeout=.2, retries=0)

    def __str__(self):
        return "Printer[%s] snmpmodel: %s snmpstatus: %s snmpmedia: %s printjobs: %d\n" % (
                self.name, self.snmpmodel, self.snmpstatus, self.snmpmedia, len(self.printjobs))

    # updatestatus
    # This is called from the SNMP process to update the printer status using SNMP
    #
    def updatestatus(self):

        oldstatus = self.snmpstatus
        #print('Printer:updatestatus[%s]: %s' % (self.name, self.snmpsession))
        try:
            data = self.snmpsession.get('iso.3.6.1.4.1.11.2.4.3.1.2.0')
            s = safe_str(self.name, data.value, 'SNMPStatus')
            if s != '':
                self.snmpvalue = s
        except:
            self.snmpvalue = ''

        try:
            data = self.snmpsession.get('iso.3.6.1.2.1.43.8.2.1.12.1.1')
            s = safe_str(self.name, data.value, 'SNMPMedia')
            if s != '':
                self.snmpmedia = s
        except:
            self.snmpmedia = ''

        try:
            data = self.snmpsession.get('iso.3.6.1.2.1.25.3.2.1.3.1')
            s = safe_str(self.name, data.value, 'SNMPModel')
            if s != '':
                self.snmpmodel = s
        except:
            self.snmpmodel = ''

        if self.snmpvalue == '':
            self.snmpstatus = SNMPStatus.NOTAVAILABLE
            self.snmpinfo = 'Not Available'
        elif re.match(r'READY', self.snmpvalue):
            self.snmpstatus = SNMPStatus.READY
            self.snmpinfo = 'Ready'
        elif re.match(r'BUSY', self.snmpvalue):
            self.snmpstatus = SNMPStatus.BUSY
            self.snmpinfo = 'Busy'
        elif re.match(r'PRINTING', self.snmpvalue):
            self.snmpstatus = SNMPStatus.PRINTING
            self.snmpinfo = 'Printing'
        elif re.match(r'COVER OPEN', self.snmpvalue):
            self.snmpstatus = SNMPStatus.COVEROPEN
            self.snmpinfo = 'Printer Cover Open'
        elif re.match(r'ERROR', self.snmpvalue):
            self.snmpstatus = SNMPStatus.ERROR
            self.snmpinfo = 'Error '
        else:
            log('[%s]: unknown: %s'  % (self.name, self.snmpvalue))
            self.snmpstatus = SNMPStatus.UNKNOWN
            self.snmpinfo = 'Unknown'

        if oldstatus != self.snmpstatus:
            #print('Printer:updatestatus[%s]: %s %s'  % (self.name, getTimeNow(), self.snmpstatus.name))
            log('[%s] %s -> %s' % (self.name, oldstatus, self.snmpstatus.name))

    # add a print job to the print jobs queue
    #
    def add(self, pool, data):
        self.printjobs.append(Job(pool, data))
        return

    # check if there are jobs queued to this printer and we are currently active
    #
    def checkforjobs(self):
        if len(self.printjobs) == 0:
            #log('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s NO JOBS' % (self.name, self.status, self.snmpstatus, len(self.printjobs)))
            #log('Printer:checkforjobs[%s] snmp: %s jobs: %s NO JOBS' % (self.name, self.snmpstatus, len(self.printjobs)))
            return False
        if self.snmpstatus != SNMPStatus.READY:
            log('[%s] snmp: %s jobs: %s SNMP NOT READY' % (self.name, self.snmpstatus, len(self.printjobs)))
            return False

        if self.sending:
            log('[%s] snmp: %s jobs: %s Already Sending' % (self.name, self.snmpstatus, len(self.printjobs)))
            return False

        log('[%s] snmp: %s jobs: %s HAVE JOBS' % (self.name, self.snmpstatus, len(self.printjobs)))

        # get current job and make a copy for working with
        self.currentjob = self.printjobs.pop(0)
        #print('Printer:checkforjobs[%s] job: %s' % (self.name, self.currentjob))
        #self.senddata = list(self.currentjob.data)
        #print('Printer:checkforjobs[%s] data: %s' % (self.name, self.senddata))
        self.sending = True

        return True

    def getJobData(self):
        return list(self.currentjob.data)

    # finished
    # Called when the print job has been finished (sent to printer). The flag is set to True for
    # success and False for possible failure.
    #
    def finished(self, flag):
        self.sending = False
        log('[%s] finished' % (self.name))
        job = self.currentjob
        self.currentjob = None
        #print('Printer:finished: currentjob: %s' % (job))
        pool = job.pool
        #print('Printer:finished: pool: %s' % (pool))

        # if there was a possible failure to deliver the print job, requeue to send again.
        #
        if not flag:
            pool.recv(job.data)
            self.errors += 1
        else:
            self.jobsFinished += 1

    def __repr__(self):
        return "Printer[%s] snmpmodel: %s snmpstatus: %s snmpmedia: %s printjobs: %d\n" % (
                self.name, self.snmpmodel, self.snmpstatus, self.snmpmedia, len(self.printjobs))
