
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
from pool import Pool
from status import StatusPort


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
                        #str = "\nSocketInfo[%s:%s] %s\nRECV: %s" % (self.port, self.portname, self.porttype.name, len(self.recvdata))
                        str = "\nXSocketInfo[%s:%s] %s" % (self.port, self.portname, self.porttype.name)
                elif self.senddata is not None and len(self.senddata) > 0:
                        #str = "\nSocketInfo[%s:%s] %s\nSEND: %s" % (self.port, self.portname, self.porttype.name, len(self.senddata))
                        str = "\nXSocketInfo[%s:%s] %s" % (self.port, self.portname, self.porttype.name)
                else:
                        str = "\nXSocketInfo[%s:%s] %s NO DATA" % (self.port, self.portname, self.porttype.name)
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
                for p,v in self.sockets.iteritems(): res += str(v)
                return res
                #return "\nSockets: %s\n" % (self.sockets)

#
# Status
#
class Status( object ):

        def __init__(self, port):
                self.port = port
                self.ds = []
                self.sent = 0


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

                self.poolRecvSockets = []
                self.printerSendSockets = []
                self.statusSendSockets = []

                self.socketMap = SocketMap()

                for p, v in pools.iteritems():
                        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        server.setblocking(0)
                        server.bind(('localhost', v.port))
                        server.listen(5)
                        self.poolListenSockets.append(server)
                        self.socketMap.add(server, v.port, SocketType.LISTEN, v.name, None, None)

                for p, v in statusPorts.iteritems():
                        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        server.setblocking(0)
                        server.bind(('localhost', v.port))
                        server.listen(5)
                        self.statusListenSockets.append(server)
                        self.socketMap.add(server, v.port, SocketType.LISTEN, v.name, None, None)

                print('Server:__init__[] self.socketMap: %s' % (self.socketMap))


        def SNMPStatus(self):
                status = ''
                for p, v in self.printers.iteritems():
                        if v.snmpstatus != SNMPStatus.READY:
                                status += '[ %s: %s ]\n' % (p, v.snmpinfo)
                return status

        def server(self):
                return self.server


        # startSendJob
        # initiate a connection to a printer to send a printer job to it
        #
        def startSendJob(self, printer):

                print('Server:startsend[ %s] testport: %s printer: %s' % (printer.name, printer.testport, printer))
                client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                #self.poolRecvSockets.append(client)
                self.printerSendSockets.append(client)
                self.socketMap.add(client, 0, SocketType.SEND, printer.name, printer.getJobData(), printer)
                client.setblocking(0)
                client.connect_ex(('127.0.0.1', printer.testport))


        def select(self):

                #print('***\nServer:Listen self.socketMap: %s\n***' % (self.socketMap))
                timeout = 10

                input_fds = self.poolListenSockets + self.statusListenSockets + self.poolRecvSockets
                output_fds = self.printerSendSockets + self.statusSendSockets

                readable, writeable, exceptional = select.select(input_fds, output_fds, input_fds, timeout)

                for e in exceptional:
                        print("******************************************\n\n")
                        print("******************************************\n\n")
                        client = self.socketMap.get(e)
                        print('Server:select:client:exceptional[%s:%s]:' % (clean.port, client.portname))

                for r in readable:
                        if r in self.poolRecvSockets:
                                connection = self.socketMap.get(r)

                                # no data or exception indicates other end has closed
                                # the connection
                                #
                                try:
                                        #data = r.recv(1024, socket.MSG_DONTWAIT)
                                        data = r.recv(1024)
                                        if data:
                                                self.socketMap.appendrecvdata(r, data)
                                                #print('Server:select:readable:data[%s}: len: %s' % (connection, len(data)))
                                                continue
                                        else:
                                                pass
                                except:
                                        pass

                                print('Server:select:readable:data[%s:%s}: no data: closing %s' % (connection.port, connection.portname, r.getpeername()) )
                                #print('Server:select:readable:data[%s}: pool: %s data: %s' % (connection, connection.portname, self.socketMap.getallrecvdata(r) ))
                                self.poolPorts[connection.portname].recv(self.socketMap.getallrecvdata(r))
                                self.poolRecvSockets.remove(r)
                                self.socketMap.remove(r)
                                r.close()
                                continue

                        if r in self.poolListenSockets:
                                client = self.socketMap.get(r)
                                fd, client_address = r.accept()
                                self.poolRecvSockets.append(fd)
                                self.socketMap.add(fd, client.port, SocketType.RECV, client.portname, None, None)
                                print('Server:select:readable:client[%s:%s]: poolListenSockets: accept from %s'  % (client.port, client.portname, client_address))
                                continue

                        if r in self.statusListenSockets:

                                client = self.socketMap.get(r)
                                fd, client_address = r.accept()

                                self.statusSendSockets.append(fd)
                                d = [self.SNMPStatus(),]
                                print('Server:select:readable:client[%s:%s]: SNMPStatus data: %s'  % (client.port, client.portname, d))
                                self.socketMap.add(fd, 0, SocketType.SEND, client.portname, (d), None)

                                print('Server:select:readable:client[%s:%s]: poolListenSockets: accept from %s'  % (client.port, client.portname, client_address))
                                continue

                        continue

                for w in writeable:
                        #print('Server:select:writeable: w: %s' % w)
                        client = self.socketMap.get(w)
                        #print('Server:select:writeable: client: %s' % client)

                        d = client.getsenddata()

                        if d is None:
                                print('Server:select:writable[%s:%s]: NO DATA CLOSE: %s' % (client.port, client.portname, socket.error))


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
                        
                        try:
                                sent = w.send(d, socket.MSG_DONTWAIT)
                                #print('Server:select:writable[%s]: sending: %d sent: %d' % (client, len(d), sent))
                        except:
                                print('Server:select:writable[%s:%s]: WRITABLE ERROR %s' % (client.port, client.portname, socket.error))
                                w.close()
                                self.printerSendSockets.remove(w)
                                client.client.finished(True)
                                self.socketMap.remove(w)
                        continue




