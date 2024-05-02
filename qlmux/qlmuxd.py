#!/usr/bin/python3
# -*- coding: utf-8 -*-
# vim: syntax=python expandtab

__version__ = "0.3.4"

import select
import socket
import sys
#import Queue
import datetime
import jsoncfg
import json
from time import sleep
from queue import Queue
from threading import Thread, Event
import signal
from pysnmp.proto import api


from .utils import log

from .services import Server
from .printer import PrinterStatus, Printer
from .pool import Pool
from .status import StatusPort
from .snmp import SNMPStatus, SNMPServer
from .discovery import DiscoveryThread

getTimeNow = datetime.datetime.now

#def log(s):
#        print('%s %s' % (getTimeNow().strftime('%H:%M:%S'), s))


class QLMuxd(Thread):

    QLMux_Pools = [
        {'name':"small_left", 'listen':9101, 'media':["62mm x 100mm",  "62mm x 100mm / 2.4\" x 3.9\"",             ],}, 
        {'name':"small_right", 'listen':9102, 'media':["62mm x 100mm",  "62mm x 100mm / 2.4\" x 3.9\"",            ],}, 
        {'name':"large_left", 'listen':9103, 'media':["102mm x 152mm", "102mm / 4\"", "102mm x 152mm / 4\" x 6\"", ],}, 
        {'name':"large_right", 'listen':9104, 'media':["102mm x 152mm", "102mm / 4\"", "102mm x 152mm / 4\" x 6\"",],}, 
        ]

    QLMux_StatusPorts = [ {'name': "status", 'listen': 9100 }, ]

    def __init__(self, stopEvent=None, changeEvent=None, snmpDiscoveredQueue=None, snmpStatusQueue=None):
        super(QLMuxd, self).__init__()
        self.stopEvent = stopEvent
        self.changeEvent = changeEvent
        self.snmpDiscoveredQueue = snmpDiscoveredQueue
        self.snmpStatusQueue = snmpStatusQueue

        self.Printers = dict()
        self.Pools = dict()
        self.StatusPorts = dict()

        cfgs = ['/usr/local/etc/qlmuxd.cfg', 'qlmuxd.cfg']

        #self.config = None
        #for c in cfgs:
        #    try:
        #        self.config = jsoncfg.load_config(c)
        #        break
        #    except Exception as e:
        #        log('QLMuxd: error cannot open %s, Exception: %s' % (c, e))
        #        continue

        #if self.config is None:
        #    log('QLMuxd: error cannot open either: %s' % cfgs)
        #    exit(1)


        # XXX Need to check if name or model has changed

    def run(self):
        # finished
        #print('config: %s' % config)

        log('Config: Printers')

        SNMP = SNMPServer(self.Printers)
        for pool in self.QLMux_Pools:
            self.Pools[pool['name']] = Pool( name=pool['name'], listen=pool['listen'], media=pool['media'],)

        for port in self.QLMux_StatusPorts:
            self.StatusPorts[port['name']] = StatusPort(port['name'], port['listen'])


    #        Printers = {
    #            'ql710w1': Printer('ql710w1', 9101),
    #            'ql710w2': Printer('ql710w2', 9102),
    #            'ql710w3': Printer('ql710w3', 9103),
    #            #'ql1060n0': Printer('192.168.40.99', 9106),
    #            'ql1060n1': Printer('ql1060n1', 9104),
    #            'ql1060n2': Printer('ql1060n2', 9105),
    #        }
    #
    #        OldPools = {
    #            'small1': Pool('small1', 9001, (Printers['ql710w1'], Printers['ql710w2']), (Printers['ql710w3'],)),
    #            'small2': Pool('small2', 9002, (Printers['ql710w3'], Printers['ql710w2']), (Printers['ql710w1'],)),
    #            'large1': Pool('large1', 9003, (Printers['ql1060n1'], ), (Printers['ql1060n2'],)),
    #            'large2': Pool('large2', 9004, (Printers['ql1060n2'], ), (Printers['ql1060n1'],)),
    #        }
    #
    #        StatusPorts = {
    #            'snmp': StatusPort('snmp', 9000),
    #        }



        #SNMP = SNMPServer(Printers)
        sleep(2)
        MyServer = Server(self.Pools, self.StatusPorts, self.Printers)

        firsttime = True
        lasttime = getTimeNow()


        # XXX: need to pass changeEvent to all modules so we can wait on it
        # while changeEvent.wait():
        while not self.stopEvent.is_set():

            log('QLMuxd: printers: %s' % (self.Printers.keys(),))
            for i, (p, v) in enumerate(self.Pools.items()):
                log('QLMuxd[%d] %s' % (i, v))

            if self.changeEvent.is_set():
                log('QLMuxd: changeEvent is set')
                self.changeEvent.clear()

            QLPrinters = [('NC-11004h', 'QL-1060N', 'large'), 
                          ('NC-16002w', 'QL-710W', 'small'), 
                          ('NC-18002w', 'QL-720NW', 'small'), ]

            while not self.snmpDiscoveredQueue.empty():
                hostaddr, hostname, sysdescr, macAddress, serialNumber = self.snmpDiscoveredQueue.get()
                if 'Brother' not in sysdescr:
                    continue
                for nc, m, s in QLPrinters:
                    if nc not in sysdescr:
                        continue
                    #self.checkPrinter(hostname, hostaddr, sysdescr, macAddress, serialNumber, 9100, m, s)
                    #def checkPrinter(self, name, hostname, sysdescr, macAddress, serialNumber, port, model, size):
                        # XXX need to use serial number to identify printers
                    if hostaddr not in self.Printers:
                        self.Printers[hostaddr] = Printer(hostname, hostaddr, sysdescr, macAddress, serialNumber, port, m, s)
                        for pool in self.QLMux_Pools:
                            if s in pool['name']:
                                self.Pools[pool['name']].addPrinter(self.Printers[hostaddr])
                                break


                #if p in Printers:
                #    Printers[p].updatestatus()
                #else:
                #    log('QLMuxd: SNMP Discovered: Printer not in Printers: %s' % p)


            #print('\n******************************')
            #print('\nMain: .... %3.1f' % (getTimeNow() - lasttime).total_seconds())


            #if firsttime or (getTimeNow() - lasttime).total_seconds() > 2:
            #       print('\nMain: updating status ....')
            #       firsttime = False
            #       for p,v in Printers.items():
            #               v.updatestatus()
            #       lasttime = getTimeNow()


            #print('\nMain: Listening ....')
            if not MyServer.select():
                log("exiting")
                break

            #print('\nMain: Processing Received ....')
            for p, v in self.Pools.items():
                v.forward()

            #print('\nMain: Forwarding Queued ....')
            for p, v in self.Printers.items():
                if v.checkforjobs():
                    MyServer.startSendJob(v)

            #for p, v in StatusPorts.items():
            #       if v.checkforjobs():
            #               Server.startsend(v)



#Pools = {
#    9001: ('ql710w1', 'ql710w2', 'ql710w3')
#    9002: ('ql710w3', 'ql710w2', 'ql710w1')
#    9003: ('ql1060n1', 'ql1060n2')
#    9004: ('ql1060n2', 'ql1060n1')
#}

#DataQueues = {
#    9001: None
#    9002: None
#    9003: None
#    9004: None
#}

#Status = {
#    'ql710w1' : None
#    'ql710w2' : None
#    'ql710w3' : None
#    'ql1060n1' : None
#    'ql1060n2' : None
#}


#
# QLMux listens on the ports to accept binary data that it will forward to the printers
# in the associated pool for each port.
#
# The binary data (typically under 10 kbytes) is kept in memory until it can be delivered. The intended
# design is for about a half dozen printers with a load of about one label per second per printer maximum.
#
# A status is kept for each printer so that fall over can be used to do the following:
#
#   1. Level load across the printers
#   2. Ensure that printers that are not available or not working are not used
#   3. Minimize printing delays
#   4. Ensure that all labels are printed, duplicates are allowed.
#
# Depending on the printer status, when data has arrived and is in the DataQueue, QLMux will attempt
# to deliver to the first available printer in the associated Pool.
#


#
# Printer Status
#
# There appear to be several ways that we can detect problems with printing.
#
#   1. NOT_FOUND - Cannot open port 9100 to the destination.
#   2. TIMEOUT - All data was not accepted while sending for printing.
#   3. COVER_OPEN - SNMP status check told us that the cover was open.
#   4. ERROR - SNMP status check told us that the printer was in error mode.
#

#
#

def qlmuxmain():
    changeEvent = Event()
    stopEvent = Event()
    snmpDiscoveredQueue = Queue()
    snmpStatusQueue = Queue()

    def signal_handler(signal, frame):
        print('QLMuxd: signal_handler')
        stopEvent.set() 
        changeEvent.set()

    signal.signal(signal.SIGINT, signal_handler)

    threads = []
    log('main: snmpDiscoveredQueue: %s' % (snmpDiscoveredQueue,), )
    threads.append(DiscoveryThread(name='broadcast_agent_discovery v1', api_version=api.protoVersion1, 
                                   changeEvent=changeEvent, stopEvent=stopEvent, 
                                   snmpDiscoveredQueue=snmpDiscoveredQueue))
    threads.append(DiscoveryThread(name='broadcast_agent_discoveryv2c', api_version=api.protoVersion2c, 
                                   changeEvent=changeEvent, stopEvent=stopEvent, 
                                   snmpDiscoveredQueue=snmpDiscoveredQueue))
    [t.start() for t in threads]
    
    server = QLMuxd(stopEvent=stopEvent, changeEvent=changeEvent, snmpDiscoveredQueue=snmpDiscoveredQueue, snmpStatusQueue=snmpStatusQueue)
    log('qlmuxmain: QLMuxd server created')
    server.start()
    log('qlmuxmain: waiting for stopEvent')
    stopEvent.wait()

    log('qlmuxmain: joining threads')
    [t.join() for t in threads if t.is_alive()]

    log('qlmuxmain: Waiting for server join')
    server.join()

    log('qlmuxmain: Done')


if __name__ == '__main__':
    qlmuxmain()


