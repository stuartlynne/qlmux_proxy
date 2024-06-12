#!/usr/bin/python3
# -*- coding: utf-8 -*-
# vim: syntax=python expandtab

__version__ = "1.0.1"

from flask import Flask, render_template, render_template_string, Response, request
import json
import sys
import asyncio
from queue import Queue
import argparse
import time
import signal
from threading import Thread, Event
from werkzeug.serving import make_server
from pysnmp.proto import api

from .flaskserver import FlaskServer
from .qlmuxd import QLMuxd
from .discovery import DiscoveryThread
from .snmpthreads import PrinterSNMPThread, ImpinjSNMPThread
from .pythonproxy import ImpinjTCPProxy
from .utils import log


class RaceProxy(Thread):
    def __init__(self, stopEvent=None, changeEvent=None,
                             printerResetEvent=None, impinjResetEvent=None,
                 snmpDiscoveredQueue=None, flaskServer=None, qlmuxd=None):
        super().__init__()
        self.stopEvent = stopEvent
        self.changeEvent = changeEvent
        self.printerResetEvent = printerResetEvent
        self.impinjResetEvent = impinjResetEvent
        self.snmpDiscoveredQueue = snmpDiscoveredQueue
        self.flaskServer = flaskServer
        self.qlmuxd = qlmuxd
        self.printerStatusQueue = Queue()     # queue for printer status updates
        self.impinjStatusQueue = Queue()      # queue for Impinj status updates
        self.printers = {}
        self.impinjs = {}


    def run(self):
        while self.changeEvent.wait():
            self.changeEvent.clear()
            if self.stopEvent.is_set():
                # stop all threads except the Flask server
                # stop the Flask flaskServer
                #flaskServer.shutdown()
                #log('flaskServer shutdown', )
                break
            if self.printerResetEvent.is_set():
                log('printerResetEvent', )
                time.sleep(2)
                self.printers = {}
                self.printerResetEvent.clear()
            if self.impinjResetEvent.is_set():
                log('impinjResetEvent', )
                time.sleep(2)
                self.impinjs = {}
                self.impinjResetEvent.clear()   
            while not self.snmpDiscoveredQueue.empty():
                #hostaddr, hostname, sysdescr = snmpDiscoveredQueue.get()
                hostaddr, hostname, sysdescr, macAddress, serialNumber = self.snmpDiscoveredQueue.get()
                #log('snmpDiscoveredQueue get: %s' % (snmpDiscoveredQueue.get(),), )
                match sysdescr:
                    case x if 'Impinj' in x:
                        #log(f'Impinj: {hostaddr}: {hostname} {sysdescr}', )
                        if hostaddr not in self.impinjs:
                            self.impinjs[hostaddr] = ImpinjSNMPThread(
                                hostname=hostname, hostaddr=hostaddr, sysdescr=sysdescr, 
                                changeEvent=self.changeEvent, stopEvent=self.impinjResetEvent,
                                impinjStatusQueue=self.impinjStatusQueue)
                            self.impinjs[hostaddr].start()
                        else:
                            self.impinjs[hostaddr].updateLastTime()

                    case x if 'Brother' in x:
                        #log(f'Brother: {hostaddr}: {hostname} {sysdescr}', )
                        #log('main: printerStatusQueue: %s' % (printerStatusQueue,), )
                        if hostaddr not in self.printers:
                            self.printers[hostaddr] = PrinterSNMPThread(
                                hostname=hostname, hostaddr=hostaddr, sysdescr=sysdescr, 
                                changeEvent=self.changeEvent, stopEvent=self.printerResetEvent,
                                printerStatusQueue=self.printerStatusQueue)
                            self.printers[hostaddr].start()
                        else:
                            self.printers[hostaddr].updateLastTime()
                        pass
            while not self.printerStatusQueue.empty():
                printerStatus = self.printerStatusQueue.get()
                self.flaskServer.printerUpdate(printerStatus)
                if self.qlmuxd is not None:
                    self.qlmuxd.printerUpdate(printerStatus)
                #self.qlmuxd.printerUpdate(printerStatus)
                #printer = printerStatusQueue.get()
                #log(f'printerStatusQueue get: {printer}', )
            while not self.impinjStatusQueue.empty():
                #log(f'impinjStatusQueue get: {impinjStatusQueue.get()}', )
                self.flaskServer.impinjUpdate(self.impinjStatusQueue.get())
                #printer = printerStatusQueue.get()

            # look for timed out printers
            self.printers = {k: v for k, v in self.printers.items() if v.is_alive()}

            # look for threads that have finished
            for k, v in self.printers.items():
                if not v.is_alive():
                    v.join()
                    del self.printers[k]

        # wait for all threads to finish
        for k, v in self.printers.items():
            if v.is_alive():
                v.join()
        log('exiting', ) 

def raceproxymain():

    changeEvent = Event()
    stopEvent = Event()
    sigintEvent = Event()
    changeEvent.clear()
    stopEvent.clear()
    sigintEvent.clear()

    printerResetEvent = Event()
    printerResetEvent.clear()
    impinjResetEvent = Event()
    impinjResetEvent.clear()

    # create the queues
    snmpDiscoveredQueue = Queue()        # queue for SNMP discovery



    def sigintHandler(signal, frame):
        log('SIGINT received %s' % (signal,), )
        stopEvent.set()
        printerResetEvent.set()
        impinjResetEvent.set()
        changeEvent.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    #log('main: printerStatusQueue: %s' % (printerStatusQueue,), )

    impinjTCPProxy = ImpinjTCPProxy(stopEvent=stopEvent, changeEvent=changeEvent)
    qlmuxd = QLMuxd(stopEvent=stopEvent, changeEvent=changeEvent, )
    flaskServer = FlaskServer(impinjTCPProxy=impinjTCPProxy, qlmuxd=qlmuxd, 
                              printerResetEvent=printerResetEvent, impinjResetEvent=impinjResetEvent)

    threads = {'flaskserver': flaskServer, 'qlmuxd': qlmuxd, 'impinjTCPProxy': impinjTCPProxy}
    #log('main: snmpDiscoveredQueue: %s' % (snmpDiscoveredQueue,), )

    threads['discoveryv1'] = DiscoveryThread(name='broadcast_agent_discovery v1', av='v1',
                                   changeEvent=changeEvent, stopEvent=stopEvent, 
                                   snmpDiscoveredQueue=snmpDiscoveredQueue)

    threads['discoverv2'] = DiscoveryThread(name='broadcast_agent_discoveryv2c', av='v2c',
                                   changeEvent=changeEvent, stopEvent=stopEvent, 
                                   snmpDiscoveredQueue=snmpDiscoveredQueue)

    threads['RaceProxy'] = RaceProxy(stopEvent=stopEvent, changeEvent=changeEvent, 
                             printerResetEvent=printerResetEvent, impinjResetEvent=impinjResetEvent,
                             snmpDiscoveredQueue=snmpDiscoveredQueue, 
                             flaskServer=flaskServer, qlmuxd=qlmuxd)

    [v.start() for k, v in threads.items()]

    stopEvent.wait()

    log('main: stopping flaskServer')
    flaskServer.shutdown()
    log('main: joining threads')
    #[t.join(4) for t in threads if t.is_alive()]
    for k, v in threads.items():
        log(f'main: {k} is_alive: {v.is_alive()}')
        if v.is_alive():
            log(f'main: joining {k}')
            v.join()
            log(f'main: joined {k}')
    log('main: stopping threads')

    #first = True
    #count = 0
    #while True:
    #    finished = True
    #    for v in threads:
    #        if v is not None:
    #            finished &= join(v, count)
    #    if finished:
    #        break
    #    count += 1


if __name__ == '__main__':

    raceproxymain()

