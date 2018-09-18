# -*- coding: utf-8 -*-
# Set encoding default for python 2.7

import sys
import itertools
import datetime
from Queue import Queue, Empty
from enum import Enum
#from easysnmp import snmp_get, snmp_set, snmp_walk
from easysnmp import Session
import re
import select
import socket
from threading import Thread as Process
from time import sleep



getTimeNow = datetime.datetime.now

def xsafe_str(obj):
        try:
                s = str(obj)

        except UnicodeEncodeError:
                print('safe_str: caught:')
                s = obj.encode('ascii', 'ignore').decode('ascii')
        return s

def safe_str(s1,msg):
        s = ''
        try:
                s = str(s1)
                print('safe_str[%s]: OK: "%s"' % (msg, s))

        except UnicodeEncodeError:
                #s = s1.encode('ascii', 'ignore').decode('ascii')
                print('safe_str[%s]: CAUGHT: "%s"' % (msg, s))

        return s




from snmp import SNMPStatus

class PrinterStatus (Enum):
	UNKNOWN = 0
	NOTAVAILABLE = 1
	OK = 2
	PRINTING = 3



class Job( object ):
	def __init__(self, pool, data):
		self.pool = pool
		self.data = data

	def __repr__(self):
		return "\nJob[%s] %s " % ( self.pool, len(self.data))


#
# Printer
# Destinations for data.
#
#
class Printer( object ):

	def __init__(self, name, testport, model):
		self.name = name
		self.testport = testport
		self.model = model
		self.snmpstatus = SNMPStatus.UNKNOWN
		self.snmpvalue = ''
                self.snmpinfo = ''
		self.snmpmedia = 'UNKNOWN MEDIA'
		self.snmpmodel = 'UNKNOWN MODEL'
		self.fd = None
		self.pool = None
		self.printjobs = []
		self.currentjob = None
		self.senddata = None
		self.sending = False
		self.jobsfinished = 0
		self.errors = 0

		self.snmpsession = Session(hostname=name, community='public', version=1, timeout=.2, retries=0)


	# updatestatus
        # This is called from the SNMP process to update the printer status using SNMP
	#
	def updatestatus(self):

		oldstatus = self.snmpstatus
		#print('Printer:updatestatus[%s]: %s' % (self.name, self.snmpsession))
		try:
			data = self.snmpsession.get('iso.3.6.1.4.1.11.2.4.3.1.2.0')
			s = safe_str(data.value, 'SNMPStatus')
                        if s is not '':
                                self.snmpvalue = s
		except:
			self.snmpvalue = ''

		try:
			data = self.snmpsession.get('iso.3.6.1.2.1.43.8.2.1.12.1.1')
                        s = safe_str(data.value, 'SNMPMedia')
                        if s is not '':
                                self.snmpmedia = s
		except:
			self.snmpmedia = ''

		try:
			data = self.snmpsession.get('iso.3.6.1.2.1.25.3.2.1.3.1')
                        s = safe_str(data.value, 'SNMPModel')
                        if s is not '':
                                self.snmpmodel = s
		except:
			self.model = ''

		if self.snmpvalue == '':
			self.snmpstatus = SNMPStatus.NOTAVAILABLE
                        self.snmpinfo = 'Not Available, check if powered off or not plugged in'
		elif re.match(r'READY', self.snmpvalue):
			self.snmpstatus = SNMPStatus.READY
                        self.snmpinfo = 'Ready'
		elif re.match(r'BUSY', self.snmpvalue):
			self.snmpstatus = SNMPStatus.BUSY
                        self.snmpinfo = 'Busy'
		elif re.match(r'PRINTING', self.snmpvalue):
			self.snmpstatus = SNMPStatus.PRINTING
                        self.snmpinfo = 'Printing'
		elif re.match(r'COVER OPEN', self.snmpvalue):
			self.snmpstatus = SNMPStatus.COVEROPEN
                        self.snmpinfo = 'Printer Cover Open, close cover'
		elif re.match(r'ERROR', self.snmpvalue):
			self.snmpstatus = SNMPStatus.ERROR
                        self.snmpinfo = 'Error, jammed, out of labels or wrong labels'
		else:
			print('Printer:updatestatus[%s]: unknown: %s'  % (self.name, self.snmpvalue))
			self.snmpstatus = SNMPStatus.UNKNOWN
                        self.snmpinfo = 'Unknown'

		if oldstatus != self.snmpstatus:
			#print('Printer:updatestatus[%s]: %s %s'  % (self.name, getTimeNow(), self.snmpstatus.name))
                        print('%s [%s] %s -> %s' % (getTimeNow().strftime('%H:%M:%S'), self.name, oldstatus, self.snmpstatus.name))

	# add a print job to the print jobs queue
	#
	def add(self, pool, data):
		self.printjobs.append(Job(pool, data))
		return

	# check if there are jobs queued to this printer and we are currently active
	#
	def checkforjobs(self):
		if len(self.printjobs) == 0:
			#print('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s NO JOBS' % (self.name, self.status, self.snmpstatus, len(self.printjobs)))
			return False
		if self.snmpstatus != SNMPStatus.READY:
			#print('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s SNMP NOT READY' % (self.name, self.status, self.snmpstatus, len(self.printjobs)))
			return False

		if self.sending:
			#print('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s Already Sending' % (self.name, self.status, self.snmpstatus, len(self.printjobs)))
			return False

		#print('Printer:checkforjobs[%s] status: %s snmp: %s jobs: %s HAVE JOBS' % (self.name, self.status, self.snmpstatus, len(self.printjobs)))

		# get current job and make a copy for working with
		self.currentjob = self.printjobs.pop(0)
		#print('Printer:checkforjobs[%s] job: %s' % (self.name, self.currentjob))
		#self.senddata = list(self.currentjob.data)
		#print('Printer:checkforjobs[%s] data: %s' % (self.name, self.senddata))
		self.sending = True

		return True

	def getJobData(self):
		return list(self.currentjob.data)

        # finished
        # Called when the print job has been finished (sent to printer). The flag is set to True for 
        # success and False for possible failure.
        #
	def finished(self, flag):
		self.sending = False
		#print('Printer:finished: %s' % (self))
		job = self.currentjob
		self.currentjob = None
		#print('Printer:finished: currentjob: %s' % (job))
		pool = job.pool
		#print('Printer:finished: pool: %s' % (pool))

                # if there was a possible failure to deliver the print job, requeue to send again.
                #
		if not flag:
			pool.recv(job.data)
                        self.errors += 1
                else:
                        self.jobsfinished += 1

	def __repr__(self):
		print( "Printer[%s]" % ( self.name))
		print( "Printer[%s] snmpmodel: %s" % ( self.name, self.snmpmodel))
		print( "Printer[%s] snmpstatus: %s" % ( self.name, self.snmpstatus))
		print( "Printer[%s] snmpmedia: %s" % ( self.name, self.snmpmedia))
		print( "Printer[%s] len: %d" % ( self.name, len(self.printjobs)))
		return "Printer[%s] snmpmodel: %s snmpstatus: %s snmpmedia: %s printjobs: %d\n" % (
			self.name, self.snmpmodel, self.snmpstatus, self.snmpmedia, len(self.printjobs))


