# -*- coding: utf-8 -*-
# Set encoding default for python 2.7
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

    def __init__(self, name, port, media, printers, backups):
        self.name = name
        self.printers = printers
        self.backups = backups
        self.queue = Queue()
        self.port = port
        self.media = media
        self.listenfd = None
        self.datafds = []
        self.lastprinter = None
        #log('[%s] queue size: %d' % (self.name, self.queue.qsize()))
        for p in self.printers:
                log('Pool:[%s] primary: %s' % (self.name, p))
        for p in self.backups:
                log('Pool:[%s] backups: %s' % (self.name, p))
        #self.setlistenfd(None)


    # receive data to be printed
    #
    def recv(self, data):
        self.queue.put(data)
        log('[%s] recv queue size: %s ' % (self.name, self.queue ))


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

        log('[%s] forward queue size: %d' % (self.name, self.queue.qsize()))

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

    def __repr__(self):
        return "\nPool[%s] Printers: %s Backups: %s" % (self.name, self.printers, self.backups)



