# -*- coding: utf-8 -*-
# Set encoding default for python 2.7
# vim: syntax=python noexpandtab


import sys
import itertools
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


class SNMPStatus (Enum):
    UNKNOWN = 0
    NOTAVAILABLE = 1
    READY = 2
    BUSY = 3
    PRINTING = 4
    COVEROPEN = 5
    ERROR = 6


#
# SNMPServer
# This is started as a separate thread, it will poll the printers with snmp every
# two seconds to get the current status.
#
class SNMPServer( object ):

    def __init__(self, printers):
        self.printers = printers
        self.updateProcess = Process( name='SNMPUpdateProcess', target=self.SNMPProcess, )
        self.updateProcess.daemon = True
        self.updateProcess.start()

    def SNMPProcess(self):

        log('SNMPServer:SNMPProcess started')
        while True:
            for p,v in self.printers.items():
                v.updatestatus()
            sleep(2)
