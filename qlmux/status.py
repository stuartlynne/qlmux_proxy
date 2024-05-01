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

from .snmp import SNMPStatus
from .printer import PrinterStatus, Printer

#
# StatusClient
#
class StatusRequest( object ):
    def __init__(self, fd, data):
        self.fd = fd
        self.statusSent = False
        self.data = (data)

    def getsentdata(self):
        return statusRequest.statusSent

    def setsentdata(self):
        statusRequest = self.statusRequests[client]
        statusRequest.statusSent = True


#
# Status Port
#
class StatusPort( object ):
    def __init__(self, name, port):
        self.name = name
        self.port = port
        self.statusRequests = []

    def add(self, clientfd, data):
        self.statusRequests[clientfd] = StatusRequest(clientfd)

    def remove(self, clientfd):
        del sel.statusRequests[clientfd]

    def getsenddata(self):
        return list(self.currentjob.data).encode("utf-8")


    def getsentdata(self, client):
        statusRequest = self.statusRequests[client]
        return statusRequest.getsentdata()

    def setsentdata(self, client):
        statusRequest = self.statusRequests[client]
        statusRequest.setsentdata()
