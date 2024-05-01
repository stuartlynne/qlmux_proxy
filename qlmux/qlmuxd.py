#!/usr/bin/python3
# -*- coding: utf-8 -*-
# Set encoding default for python 2.7
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

from .utils import log

from .services import Server
from .printer import PrinterStatus, Printer
from .pool import Pool
from .status import StatusPort
from .snmp import SNMPStatus, SNMPServer

getTimeNow = datetime.datetime.now

#def log(s):
#        print('%s %s' % (getTimeNow().strftime('%H:%M:%S'), s))


def main():

    cfgs = ['/usr/local/etc/qlmuxd.cfg', 'qlmuxd.cfg']

    config = None
    for c in cfgs:
        try:
            config = jsoncfg.load_config(c)
            break
        except Exception as e:
            log('QLMuxd: error cannot open %s, Exception: %s' % (c, e))
            continue

    if config is None:
        log('QLMuxd: error cannot open either: %s' % cfgs)
        exit(1)

    Printers = dict()
    Pools = dict()
    StatusPorts = dict()

    #print('config: %s' % config)
    ports = config.QLMux_Ports()
    log('Config: Ports: %s' % (ports))
    for v in ports:
        log('Config: Pool Port: %s' % (v))
    ports = config.QLMux_StatusPorts()
    for v in ports:
        log('Config: Status Port: %s' % (v))

    log('Config: Printers')
    for QLMux_Printer in config.QLMux_Printers:
        log('Config: Printer: name: %s port: %s model: %s' % (QLMux_Printer.name(), QLMux_Printer.port(), QLMux_Printer.model()))
        name = QLMux_Printer.name()
        hostname = QLMux_Printer.hostname()
        port = QLMux_Printer.port()
        model = QLMux_Printer.model()
        Printers[QLMux_Printer.name()] = Printer(name, hostname, port, model);

    SNMP = SNMPServer(Printers)
    sleep(2)

    log('Config: Pools')
    for QLMux_Pool in config.QLMux_Pools:

        log('Config: Pool: name: %s' % (QLMux_Pool))

        primaries = QLMux_Pool.primaries()
        backups = QLMux_Pool.backups()
        media = QLMux_Pool.media()

        log('Config: Pool: name: %s port: %s primaries: %s backups: %s media: %s' %
                (QLMux_Pool.name(), QLMux_Pool.listen(), primaries, backups, media))

        Pools[QLMux_Pool.name()] = Pool(
                QLMux_Pool.name(),
                QLMux_Pool.listen(),
                QLMux_Pool.media(),
                [ Printers[p] for p in primaries],
                [ Printers[b] for b in backups], )


    for QLMux_StatusPort in config.QLMux_StatusPorts:
        StatusPorts[QLMux_StatusPort.name()] = StatusPort(QLMux_StatusPort.name(), QLMux_StatusPort.port())


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
    MyServer = Server(Pools, StatusPorts, Printers)

    firsttime = True
    lasttime = getTimeNow()


    while True:

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
        for p, v in Pools.items():
            v.forward()

        #print('\nMain: Forwarding Queued ....')
        for p, v in Printers.items():
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


if __name__ == '__main__':
    main()
