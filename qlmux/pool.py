
import sys
import itertools
from Queue import Queue, Empty
from enum import Enum
#from easysnmp import snmp_get, snmp_set, snmp_walk
from easysnmp import Session
import re
import select
import socket
from threading import Thread as Process
from time import sleep

from snmp import SNMPStatus
from printer import PrinterStatus, Printer

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

	def __init__(self, name, port, printers, backups):
		self.name = name
		self.printers = printers
		self.backups = backups
		self.queue = Queue()
		self.port = port
		self.listenfd = None
		self.datafds = []
		self.lastprinter = None
		print('Pool:__init__[%s] queue: %s' % (self.name, self.queue.qsize()))
		print('Pool:__init__[%s] printers: %s' % (self.name, self.printers))
		print('Pool:__init__[%s] backups: %s' % (self.name, self.backups))
		#self.setlistenfd(None)


	# receive data to be printed
	#
	def recv(self, data):
		self.queue.put(data)
		#print('Pool:recv: pool: %s data: %s ' % (self.name, self.queue ))


	# find the best printer from the list provided
	#
	def bestprinter(self, printers):
		t = None
		for p in printers:
			#print('Pool:process[%s] printer: %s' % (self.name, p))
			#print('Pool:bestprinter[%s] printer: %s status: %s snmp: %s jobs: %s' % (self.name, p.name, p.status, p.snmpstatus, len(p.printjobs)))
			if p.status == PrinterStatus.NOTAVAILABLE: continue
			if p.snmpstatus != SNMPStatus.READY: continue
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

		#print('Pool:forward[%s] queue: %s' % (self.name, self.queue.qsize()))

		printer = self.bestprinter(self.printers)

		if printer is None:
			printer = self.bestprinter(self.backups)
			if printer is not None:
				print('%s [%s] %s FORWARD BACKUP' % (getTimeNow().strftime('%H:%M:%S'), self.name, printer.name))
		else:
			print('%s [%s] %s FORWARD' % (getTimeNow().strftime('%H:%M:%S'), self.name, printer.name))

		if printer is None:
			print('%s [%s] CANNOT FIND PRINTER' % (getTimeNow().strftime('%H:%M:%S'), self.name))
			return

		self.lastprinter = printer
		printer.add(self, self.queue.get())

	def __repr__(self):
		return "\nPool[%s] Printers: %s Backups: %s" % (self.name, self.printers, self.backups)



