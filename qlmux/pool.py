# -*- coding: utf-8 -*-
# vim: syntax=python expandtab

import sys
import itertools
from queue import Queue, Empty
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
from .printer import PrinterStatus, Printer

import datetime
getTimeNow = datetime.datetime.now

#
# Printer Pools
# Associated with a single port to receive data.
# And a set of printers that the data can be sent to.
#
# Data is received and then forwarded to the best printer available.
#
#
class Pool( object ):

    def __init__(self, name=None, listen=None, media=None, printers=None, backups=None):
        log('Pool:[%s:%s] media: %s ' % (name, listen, media))
        self.name = name
        self.printers = printers if printers is not None else []
        self.backups = backups if backups is not None else []
        self.queue = Queue()
        self.listen = listen
        self.media = media
        self.listenfd = None
        self.datafds = []
        self.lastprinter = None
        self.jobsReceived = 0
        self.jobsForwarded = 0
        for p in self.printers:
            log('Pool:[%s] primary: %s' % (self.name, p))
        for p in self.backups:
            log('Pool:[%s] backups: %s' % (self.name, p))
        #self.setlistenfd(None)
    
    def __str__(self):
        return "%s Printers: %s Backups: %s" % (self.name, self.printers, self.backups)

    # XXX need to use serial number to identify printers, not name
    def addPrinter(self, printer, primary=False):
        if primary is True:
            if printer not in self.printers:
                self.printers.append(printer)
        else:
            if printer not in self.backups:
                self.backups.append(printer)

    def removePrinter(self, printer): 
        if printer in self.printers:
            self.printers.remove(printer)
        if printer in self.backups:
            self.backups.remove(printer)

    # receive data to be printed
    #
    def recv(self, data):
        self.queue.put(data)
        self.jobsReceived += 1
        log('[%s] jobsReceived: %s recv queue size: %s ' % (self.name, self.jobsReceived, self.queue ))


    # find the best printer from the list provided
    #
    def bestprinter(self, printers):
        t = None
        for p in printers:
            log('Pool:process[%s] printer: %s' % (self.name, p))
            log('Pool:bestprinter[%s] printer: %s snmp: %s media: %s jobs: %s' % (self.name, p.name, p.snmpstatus, p.snmpmedia, len(p.printjobs)))

            # check if media looks correct
            matched = False
            for m in self.media:
                log('Pool[%s]: match %s %s' % (self.name, m, p.snmpmedia))
                if not re.match(m, p.snmpmedia):
                    continue
                matched = True
                break;

            if matched is False:
                continue

            # check if model is correct
            #if p.snmpmodel != p.model:
            #    continue
            # check if READY
            if p.snmpstatus != SNMPStatus.READY and p.snmpstatus != SNMPStatus.BUSY and p.snmpstatus != SNMPStatus.PRINTING:
                continue

            if t is None:
                t = p
                continue
            if len(t.printjobs) == len(p.printjobs):
                if self.lastprinter == t:
                    t = p
            elif len(t.printjobs) > len(p.printjobs):
                t = p
            continue
        return t

    # forward queued data to best printer available
    #
    def forward(self):
        if self.queue.qsize() == 0:
            return

        log('[%s] forwarded: %s queue size: %d' % (self.name, self.jobsForwarded, self.queue.qsize()))

        printer = self.bestprinter(self.printers)

        if printer is None:
            printer = self.bestprinter(self.backups)
            if printer is not None:
                log('%s [%s] %s FORWARD BACKUP' % (getTimeNow().strftime('%H:%M:%S'), self.name, printer.name))
        else:
            log('%s [%s] %s FORWARD' % (getTimeNow().strftime('%H:%M:%S'), self.name, printer.name))

        if printer is None:
            log('%s [%s] CANNOT FIND PRINTER' % (getTimeNow().strftime('%H:%M:%S'), self.name))
            return

        if printer.snmpstatus != SNMPStatus.READY:
            log('%s [%s] PRINTER Busy' % (getTimeNow().strftime('%H:%M:%S'), self.name))
            return
        self.lastprinter = printer
        printer.add(self, self.queue.get())
        self.jobsForwarded += 1

    def __repr__(self):
        return "\nPool[%s] Printers: %s Backups: %s" % (self.name, self.printers, self.backups)
