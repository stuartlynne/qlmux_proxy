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
from .discovery import DiscoveryThread
from .snmpthreads import PrinterSNMPThread, ImpinjSNMPThread
from .pythonproxy import ImpinjTCPProxy

def raceproxy_main():

    sigintEvent = Event()
    changeEvent = Event()
    stopEvent = Event()
    sigintEvent.clear()
    changeEvent.clear()
    stopEvent.clear()

    # create the queues
    snmpDiscoveredQueue = Queue()        # queue for SNMP discovery
    printerStatusQueue = Queue()     # queue for printer status updates
    impinjStatusQueue = Queue()      # queue for Impinj status updates

    impinjTCPProxy = ImpinjTCPProxy(stopEvent=stopEvent, changeEvent=changeEvent)
    impinjTCPProxy.start()

    printers = {}
    impinjs = {}


    def sigintHandler(signal, frame):
        print('SIGINT received %s' % (signal,), file=sys.stderr)
        sigintEvent.set()
        changeEvent.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    print('main: printerStatusQueue: %s' % (printerStatusQueue,), file=sys.stderr)
    flaskServer = FlaskServer(impinjTCPProxy=impinjTCPProxy, )
    flaskServer.start()

    threads = []
    print('main: snmpDiscoveredQueue: %s' % (snmpDiscoveredQueue,), file=sys.stderr)
    threads.append(DiscoveryThread(name='broadcast_agent_discovery v1', api_version=api.protoVersion1, 
                                   changeEvent=changeEvent, stopEvent=stopEvent, 
                                   snmpDiscoveredQueue=snmpDiscoveredQueue))
    threads.append(DiscoveryThread(name='broadcast_agent_discoveryv2c', api_version=api.protoVersion2c, 
                                   changeEvent=changeEvent, stopEvent=stopEvent, 
                                   snmpDiscoveredQueue=snmpDiscoveredQueue))
    [t.start() for t in threads]
    while changeEvent.wait():
        changeEvent.clear()
        if sigintEvent.is_set():
            # stop all threads except the Flask server
            stopEvent.set()
            # stop the Flask flaskServer
            flaskServer.shutdown()
            print('flaskServer shutdown', file=sys.stderr)
            break
        while not snmpDiscoveredQueue.empty():
            hostaddr, hostname, sysdescr = snmpDiscoveredQueue.get()
            #print('snmpDiscoveredQueue get: %s' % (snmpDiscoveredQueue.get(),), file=sys.stderr)
            match sysdescr:
                case x if 'Impinj' in x:
                    #print(f'Impinj: {hostaddr}: {hostname} {sysdescr}', file=sys.stderr)
                    if hostaddr not in impinjs:
                        impinjs[hostaddr] = ImpinjSNMPThread(
                            hostname=hostname, hostaddr=hostaddr, sysdescr=sysdescr, 
                            changeEvent=changeEvent, stopEvent=stopEvent,
                            impinjStatusQueue=impinjStatusQueue)
                        impinjs[hostaddr].start()
                    else:
                        impinjs[hostaddr].updateLastTime()

                case x if 'Brother' in x:
                    #print(f'Brother: {hostaddr}: {hostname} {sysdescr}', file=sys.stderr)
                    #print('main: printerStatusQueue: %s' % (printerStatusQueue,), file=sys.stderr)
                    if hostaddr not in printers:
                        printers[hostaddr] = PrinterSNMPThread(
                            hostname=hostname, hostaddr=hostaddr, sysdescr=sysdescr, 
                            changeEvent=changeEvent, stopEvent=stopEvent,
                            printerStatusQueue=printerStatusQueue)
                        printers[hostaddr].start()
                    else:
                        printers[hostaddr].updateLastTime()
                    pass
        while not printerStatusQueue.empty():
            flaskServer.printerUpdate(printerStatusQueue.get())
            #printer = printerStatusQueue.get()
            #print(f'printerStatusQueue get: {printer}', file=sys.stderr)
        while not impinjStatusQueue.empty():
            #print(f'impinjStatusQueue get: {impinjStatusQueue.get()}', file=sys.stderr)
            flaskServer.impinjUpdate(impinjStatusQueue.get())
            #printer = printerStatusQueue.get()

        # look for timed out printers
        printers = {k: v for k, v in printers.items() if v.is_alive()}

        # look for threads that have finished
        for k, v in printers.items():
            if not v.is_alive():
                v.join()
                del printers[k]

    # wait for all threads to finish
    for k, v in printers.items():
        if v.is_alive():
            v.join()
    [t.join() for t in threads if t.is_alive()]
    print('exiting', file=sys.stderr) 


if __name__ == '__main__':

    raceproxy_main()

