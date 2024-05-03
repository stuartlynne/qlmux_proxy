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
import traceback

from .utils import *
from .snmp import SNMPStatus
from .printer import PrinterStatus, Printer, PrinterQueue

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

    def __init__(self, printers=None, **kwargs):
        self.name = kwargs['name']
        self.media = kwargs['media']
        self.listen = kwargs['listen']
        self.size = kwargs['size']
        self.queue = kwargs['queue']
        log('Pool:[%s:%s] size: %s ' % (self.name, self.listen, self.size))
        self.printers = printers
        self.queue = Queue()
        self.listenfd = None
        self.datafds = []
        self.jobsReceived = 0
        self.jobsForwarded = 0
        #self.setlistenfd(None)
    
    def __str__(self):
        return "[%s:%s:%s]" % (self.name, self.size, self.listen, )

    # XXX need to use serial number to identify printers, not name
    #def addPrinter(self, printer, primary=False):
    #    if primary is True:
    #        if printer not in self.printers:
    #            self.printers.append(printer)
    #    else:
    #        if printer not in self.backups:
    #            self.backups.append(printer)

    #def removePrinter(self, printer): 
    #    if printer in self.printers:
    #        self.printers.remove(printer)
    #    if printer in self.backups:
    #        self.backups.remove(printer)

    # receive data to be printed
    #
    def recv(self, data):
        self.queue.put(data)
        self.jobsReceived += 1
        log('[%s] jobsReceived: %s recv queue size: %s ' % (self.name, self.jobsReceived, self.queue ))


    # find the best printer from the list provided
    #

    # forward queued data to best printer available
    #
    def forward(self):
        # check if we have any work
        log('[%s] forwarded: %s queue size: %d' % (self.name, self.jobsForwarded, self.queue.qsize()))
        if self.queue.qsize() == 0:
            return

        #log('[%s] printers: %s' % (self.name, self.printers, )

        # check if we have any printers
        try:
            available = sorted([(p, v.check(self.size)) for p, v in self.printers.items() if v.check(self.size)], key=lambda x: x[1])
            log('Pool.bestprinter[%s:%s] available: %s' % (self.name, self.size, available))
        except Exception as e:
            log('Pool.bestprinter[%s:%s] Exception: %s' % (self.name, self.size, e))
            log(traceback.format_exc())
            return

        if len(available) == 0:
            log('Pool.bestprinter[%s:%s] No printers available' % (self.name, self.size))
            return  
        hostname, lastUsed = available[0]
        printer = self.printers[hostname]
        printer.add(self, self.queue.get())
        self.jobsForwarded += 1

    def __repr__(self):
        return "\nPool[%s] Printers: %s Backups: %s" % (self.name, self.printers, self.backups)
