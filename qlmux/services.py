# -*- coding: utf-8 -*-
# Set encoding default for python 2.7

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

from .snmp import SNMPStatus
#from printer import PrinterStatus, Printer
#from pool import Pool
#from status import StatusPort

import datetime

#
# Track info on Sockets
#
class SocketType (Enum):
        NONE = 0
        LISTEN = 1
        RECV = 2
        SEND = 3

class SocketInfo( object ):
        def __init__(self, socket, port, porttype, portname, senddata, client):
                self.socket = socket
                self.port = port
                self.porttype = porttype
                self.portname = portname
                self.senddata = senddata
                self.client = client
                self.recvdata = []

        #def appendsenddata(self, data):
        #        self.senddata.append(data)

        def appendrecvdata(self, data):
                self.recvdata.append(data)

        def getallrecvdata(self):
                return self.recvdata

        def getsenddata(self):
                if len(self.senddata) == 0: return None
                return self.senddata.pop(0)

        def __repr__(self):
                if self.recvdata is not None and len(self.recvdata) > 0:
                        str = "\nSocketInfo[%s:%s] %s\nRECV: %s" % (self.port, self.portname, self.porttype.name, len(self.recvdata))
                        #str = "\nSocketInfo[%s:%s] %s" % (self.port, self.portname, self.porttype.name)
                elif self.senddata is not None and len(self.senddata) > 0:
                        str = "\nSocketInfo[%s:%s] %s\nSEND: %s" % (self.port, self.portname, self.porttype.name, len(self.senddata))
                        #str = "\nSocketInfo[%s:%s] %s" % (self.port, self.portname, self.porttype.name)
                else:
                        str = "\nSocketInfo[%s:%s] %s NO DATA" % (self.port, self.portname, self.porttype.name)
                return str


#
# SocketMap
# Keep track of open sockets 
#
class SocketMap( object ):

        def __init__(self):
                self.sockets = dict()

        def add(self, socket, port, porttype, portname, senddata, client):
                self.sockets[socket] = SocketInfo(socket, port, porttype, portname, senddata, client)

        def remove(self, socket):
                del self.sockets[socket]

        def get(self, socket):
                return self.sockets[socket]

        def appendrecvdata(self, socket, data):
                self.sockets[socket].appendrecvdata(data)

        def getallrecvdata(self, socket):
                return self.sockets[socket].getallrecvdata()

        def getsenddata(self, socket):
                return self.sockets[socket].getsenddata()

        def __repr__(self):
                res = ''
                for p,v in self.sockets.items(): res += str(v)
                return res
                #return "\nSockets: %s\n" % (self.sockets)


#
# Create the server
#
class Server( object):

        def __init__(self, pools, statusPorts, printers):

                self.poolPorts = pools                  # poolsPorts are ports we listen to for printer jobs
                self.statusPorts = statusPorts          # statusPorts are ports we listen to, to report printer status
                self.printers = printers

                self.poolListenSockets = []             # list of listen sockets for pool ports
                self.statusListenSockets = []           # list of listen sockets for status ports

                self.poolRecvSockets = []               # list of recv sockets for receiving a job for a pool
                self.printerSendSockets = []            # list of send sockets for sending a job to a printer
                self.statusSendSockets = []             # list of send sockets for return status information 

                self.socketMap = SocketMap()

                #print('*********************************************')
                for p, v in pools.items():
                        log('Server: listen on %s pool Port' % v.port)
                        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        server.setblocking(0)
                        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        #server.bind(('localhost', v.port))
                        server.bind(('', v.port))
                        server.listen(5)
                        self.poolListenSockets.append(server)
                        self.socketMap.add(server, v.port, SocketType.LISTEN, v.name, None, None)

                #print('*********************************************')
                for p, v in statusPorts.items():
                        log('Server: listen on %s status Port' % v.port)
                        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                        server.setblocking(0)
                        #server.bind(('localhost', v.port))
                        server.bind(('', v.port))
                        server.listen(5)
                        self.statusListenSockets.append(server)
                        self.socketMap.add(server, v.port, SocketType.LISTEN, v.name, None, None)

                #print('Server:__init__[] self.socketMap: %s' % (self.socketMap))


        def SNMPStatus(self):
                status = ''
                for p, v in self.printers.items():

                        #print('################################################')
                        #print('SNMPStatus[%s]' % (p))

                        #print('-----------------------')
                        # test for common errors, NOTAVAILABLE, COVEROPEN, ERROR
                        if v.snmpstatus == SNMPStatus.NOTAVAILABLE:
                                status += '\n'
                                status += '[%8s: %-67s ]\n' % (p, v.snmpinfo)
                                status += '[%8s: Check if powered off or not plugged in ]\n\n' % ("")
                                continue

                        if v.snmpstatus == SNMPStatus.COVEROPEN:
                                status += '\n'
                                status += '[%8s: %-67s ]\n' % (p, v.snmpinfo)
                                status += '[%8s: Check printer cover is closed ]\n\n' % ("")
                                continue

                        if v.snmpstatus == SNMPStatus.ERROR:
                                status += '\n'
                                status += '[%8s: %-67s ]\n' % (p, v.snmpinfo)
                                status += '[%8s: Jammed, out of labels or wrong labels ]\n\n' % ("")
                                continue

                        if v.model != v.snmpmodel:
                                status += '\n'
                                status += '[%8s: Wrong Model, have %s, need %s ]\n\n' % (p, v.snmpmodel, v.model)
                                continue

                        # If we get here the printer is READY, BUSY, or PRINTING 
                        # Check that media is the correct match, currently we assume that media is same
                        # across all pools that use the same printers.
                        match = False
                        poolmedia = None
                        for p1, v1 in self.poolPorts.items():
                                printers = v1.printers + v1.backups
                                media = v1.media
                                #print('[%s] printers: %s' % (p1, printers))
                                #print('[%s] media: %s' % (p1, media))

                                #continue

                                #print('SNMPStatus[%s] %s' % (p1, v1))
                                #print('SNMPStatus[%s] printers: %s' % (p1, v1.printers))

                                for v2 in v1.printers:
                                        if v2.name != p:
                                                continue
                                        poolmedia = v1.media
                                        for m in v1.media:
                                                #print('[%s] media: "%s" == "%s"' % (p1, m, v.snmpmedia))
                                                #if m == v.snmpmedia:
                                                if re.match(m, v.snmpmedia):
                                                        match = True
                                        #print('[%s] name: %s snmpmedia: %s match: %s' % (p, v2.name, v.snmpmedia, match))
                                        break

                        if not match:
                                status += '\n'
                                status += '[%8s: Wrong Media ]\n' % (p)
                                status += '[%8s: Have %s Need %s ]\n\n' % (p, v.snmpmedia, poolmedia)
                                continue

                        status += '[%8s: %-26s %-40s ]\n' % (p, v.snmpmedia, v.snmpinfo)
                return status


        # startSendJob
        # initiate a connection to a printer to send a printer job to it
        #
        def startSendJob(self, printer):

                log('[%s] %s:%s SENDING' % (printer.name, printer.jobsfinished, printer.errors))
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.printerSendSockets.append(client)
                self.socketMap.add(client, 0, SocketType.SEND, printer.name, printer.getJobData(), printer)
                client.setblocking(0)
                #client.connect_ex(('127.0.0.1', printer.testport))
                client.connect_ex((printer.hostname, 9100))


        def select(self):

                timeout = 10

                input_fds = self.poolListenSockets + self.statusListenSockets + self.poolRecvSockets
                output_fds = self.printerSendSockets + self.statusSendSockets

                exceptional = None
                readable = None
                writeable = None
                returncode = True

                try:
                        readable, writeable, exceptional = select.select(input_fds, output_fds, input_fds, timeout)
                except:
                        returncode = False
                        pass


                if exceptional is not None:
                        for e in exceptional:
                                #print("******************************************")
                                #print("******************************************")
                                client = self.socketMap.get(e)
                                log('Server:select:client:exceptional[%s:%s]:' % (clean.port, client.portname))

                                if e in self.poolRecvSockets:
                                        log('Server:select:exceptional:data[%s:%s}: input exception: closing %s' % (connection.port, connection.portname, e.getpeername()) )
                                        self.poolPorts[connection.portname].recv(self.socketMap.getallrecvdata(e))
                                        self.poolRecvSockets.remove(e)

                                if e in output_fds:
                                        log('Server:select:exceptional:data[%s:%s}: output exception: closing %s' % (connection.port, connection.portname, e.getpeername()) )
                                        if e in self.statusSendSockets:
                                                self.statusSendSockets.remove(e)
                                        elif e in self.printerSendSockets:
                                                self.printerSendSockets.remove(e)
                                                client.client.finished(True)

                                e.close()
                                self.socketMap.remove(e)

                                continue
                #else:
                #        print("******************************************")
                #        print("******************************************")
                #        print("exceptional is None **********************")
                #        print("******************************************")
                #        print("******************************************")


                if readable is not None:
                        for r in readable:

                                # receive data coming into pool receive socket
                                if r in self.poolRecvSockets:
                                        connection = self.socketMap.get(r)

                                        # no data or exception indicates other end has closed
                                        # the connection
                                        #
                                        try:
                                                data = r.recv(1024)
                                                if data:
                                                        self.socketMap.appendrecvdata(r, data)
                                                        #print('Server:select:readable:data[%s}: len: %s' % (connection, len(data)))
                                                        continue
                                                else:
                                                        pass
                                        except:
                                                pass

                                        log('[%s:%s]: RECV no data: closing %s' % (connection.port, connection.portname, r.getpeername()) )
                                        self.poolPorts[connection.portname].recv(self.socketMap.getallrecvdata(r))
                                        self.poolRecvSockets.remove(r)
                                        self.socketMap.remove(r)
                                        r.close()
                                        continue

                                # handle an incoming connection on a pool listen port
                                if r in self.poolListenSockets:
                                        client = self.socketMap.get(r)
                                        fd, client_address = r.accept()
                                        self.poolRecvSockets.append(fd)
                                        self.socketMap.add(fd, client.port, SocketType.RECV, client.portname, None, None)
                                        #print('Server:select:readable:client[%s:%s]: poolListenSockets: accept from %s'  % (client.port, client.portname, client_address))
                                        log('[%s:%s]: LISTEN %s PRINT'  % (client.port, client.portname, client_address))
                                        continue

                                # handle an incoming connection on a status listen port
                                if r in self.statusListenSockets:

                                        client = self.socketMap.get(r)
                                        fd, client_address = r.accept()

                                        self.statusSendSockets.append(fd)
                                        d = [self.SNMPStatus(),]
                                        self.socketMap.add(fd, 0, SocketType.SEND, client.portname, (d), None)
                                        #print('Server:select:readable:client[%s:%s]: poolListenSockets: accept from %s'  % (client.port, client.portname, client_address))
                                        #print('[%s:%s]: %s STATUS'  % (client.port, client.portname, client_address))
                                        continue

                                continue

                if writeable is not None:
                        for w in writeable:
                                client = self.socketMap.get(w)

                                if w in self.statusSendSockets:
                                        s = client.getsenddata()
                                        if s is not None:
                                                d = s.encode("utf-8")
                                        else:
                                                d = None
                                elif w in self.printerSendSockets:
                                        d = client.getsenddata()

                                # no data to send to this socket, close the connection
                                if d is None:
                                        log('[%s:%s]: WRITE NO DATA CLOSE: %s' % (client.port, client.portname, socket.error))
                                        if w in self.statusSendSockets:
                                                self.statusSendSockets.remove(w)
                                        elif w in self.printerSendSockets:
                                                self.printerSendSockets.remove(w)
                                                client.client.finished(True)
                                        else:
                                                pass

                                        w.close()
                                        self.socketMap.remove(w)
                                        continue

                                # have data, send it, 

                                # XXX we are seeing problems here
                                #Traceback (most recent call last):
                                #    Traceback (most recent call last):
                                #      File "/usr/local/bin/qlmuxd", line 11, in <module>
                                #        load_entry_point('qlmux==0.3.4', 'console_scripts', 'qlmuxd')()
                                #      File "/usr/local/lib/python2.7/dist-packages/qlmux/qlmuxd.py", line 124, in main
                                #        MyServer.select()
                                #      File "/usr/local/lib/python2.7/dist-packages/qlmux/services.py", line 286, in select
                                #        sent = w.send(d, socket.MSG_DONTWAIT)
                                #       except socket.error as e:

                                try:
                                        sent = w.send(d, socket.MSG_DONTWAIT)
                                        #sent = w.send(d)

                                except Exception as e:
                                        log('[%s:%s]: len: %d WRITABLE ERROR %s' % (client.port, client.portname, len(d), e))
                                        w.close()
                                        try:
                                                self.printerSendSockets.remove(w)
                                        except:
                                                log('[%s:%s]: CAUGHT exception' % (client.port, client.portname))
                                                pass

                                        # XXX should this be False to requeue?
                                        try:
                                                client.client.finished(False)
                                        except:
                                                log('[%s:%s]: CAUGHT exception' % (client.port, client.portname))
                                                pass
                                        try:
                                                self.socketMap.remove(w)
                                        except:
                                                log('[%s:%s]: CAUGHT exception' % (client.port, client.portname))
                                                pass
                                continue

                return returncode




