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

    queues = {
            PrinterQueue.LEFT: (PrinterQueue.LEFT, PrinterQueue.CENTER, PrinterQueue.RIGHT),
            PrinterQueue.RIGHT: (PrinterQueue.RIGHT, PrinterQueue.CENTER, PrinterQueue.LEFT),
    }

    def __init__(self, printers=None, **kwargs):
        self.name = kwargs['name']
        self.media = kwargs['media']
        self.listen = kwargs['listen']
        self.size = kwargs['size']
        self.queue = kwargs['queue']
        log('Pool:[%s:%s] size: %s ' % (self.name, self.listen, self.size))
        self.printers = printers
        self.jobQueue = Queue()
        self.listenfd = None
        self.datafds = []
        self.jobsReceived = 0
        self.jobsForwarded = 0
        #self.setlistenfd(None)
    
    def __str__(self):
        return "[%s:%s:%s] %d -> %d" % (self.name, self.size, self.listen, self.jobsReceived, self.jobsForwarded)

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
        self.jobQueue.put(data)
        self.jobsReceived += 1
        log('[%s] jobsReceived: %s recv: %s queue size: %s ' % (self.name, self.jobsReceived, len(data), self.jobQueue ))


    # find the best printer from the list provided
    #

    # forward queued data to best printer available
    #
    def forward(self):
        # check if we have any work
        #log('[%s] forwarded: %s queue size: %d' % (self.name, self.jobsForwarded, self.jobQueue.qsize()))
        if self.jobQueue.qsize() == 0:
            return

        #log('[%s] printers: %s' % (self.name, self.printers, )

        # check if we have any printers
        try:
            # XXX Need to iterate across printers in each pool queue,
            #   desired queue, center, other
            for q in self.queues[self.queue]:
                available = sorted([(p, v.check(q, self.size)) for p, v in self.printers.items() if v.check(q, self.size)], key=lambda x: x[1])
                if len(available) > 0:
                    log('Pool.bestprinter[%s:%s] %s available: %s' % (self.name, self.size, q.name, available))
                    break
        except Exception as e:
            log('Pool.bestprinter[%s:%s] Exception: %s' % (self.name, self.size, e))
            log(traceback.format_exc())
            return

        if len(available) == 0:
            log('Pool.bestprinter[%s:%s] No printers available' % (self.name, self.size))
            return  
        hostname, lastUsed = available[0]
        printer = self.printers[hostname]
        printer.add(self, self.jobQueue.get())
        self.jobsForwarded += 1

    def __repr__(self):
        return "Pool[%s] Printers: %s Backups: %s" % (self.name, self.printers, self.backups)
