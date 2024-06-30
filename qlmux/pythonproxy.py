#!/usr/bin/python3
import socket
import select
import time
import sys
from threading import Thread, Event
from queue import Queue
import traceback
import signal

from .keepalive import set_keepalive
from .utils import log

class Forward:
    def __init__(self):
        self.forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        set_keepalive(self.forward, after_idle_sec=4, interval_sec=1, max_fails=3)
        self.forward.settimeout(5)

    def start(self, host, port):
        try:
            self.forward.connect((host, port))
            return self.forward
        except Exception as e:
            log('Forward.start: Exception: %s' % (e,), )
            return None

class TCPProxy(Thread):

    def __init__(self, host=None, hostport=None, target=None, targetport=None, maxconnect=None, 
                 stopEvent=None, changeEvent=None, proxyStatusQueue=None):

        super(TCPProxy, self).__init__()
        self.input_list = []
        self.maxconnect = maxconnect
        self.connected = False
        self.channel = {}
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        set_keepalive(self.server, after_idle_sec=4, interval_sec=1, max_fails=3)
        self.server.settimeout(5)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, hostport))
        self.server.listen(200)
        self.listenAddress = None
        self.host = host
        self.hostport = hostport
        self.target = target
        self.targetport = targetport
        self.stopEvent = stopEvent
        self.changeEvent = changeEvent
        self.proxyStatusQueue = proxyStatusQueue
        log('TCPProxy.__init__[%s:%s] targetport: %s' % (self.hostport, self.target, self.targetport), )

        self.dataReceived = 0
        self.messagesReceived = 0

    def update(self, proxyStatus):
        if self.proxyStatusQueue:
            if self.target: 
                log('TCPProxy.update[%s:%s] proxyStatus: %s' % (self.hostport, self.target, proxyStatus,), )
                self.proxyStatusQueue.put({self.target: proxyStatus})
            else:
                log('TCPProxy.update[%s:%s] proxyStatus: %s NO TARGET' % (self.hostport, self.target, proxyStatus,), )
        else:
            log('TCPProxy.update[%s:%s] proxyStatus: %s NO QUEUE' % (self.hostport, self.target, proxyStatus,), )

    def stop(self):
        self.update({'status': 'closing'})
        self.close_all()
        self.target = None
        self.connected = False

    # Change the target of the proxy, 
    #      - close existing connections
    #      - set the new target    
    #      - set changeEvent to signal the change
    def change(self, target=None, ):
        log('TCPProxy.change[%s:%s] target: %s)' % (self.hostport, self.target, target), )
        self.update({'status': 'closing'})
        self.close_all()
        self.target = target
        log('TCPProxy.change[%s:%s] target: %s' % (self.hostport, self.target, self.target), )
        self.dataReceived = 0
        self.messagesReceived = 0
        #for k, v in self.channel.items():
        #    v.close()
        #self.channel = {}
        self.changeEvent.set()

    def close_all(self):
        log('TCPProxy.close_all[%s:%s]' % (self.hostport, self.target), )
        for k, v in self.channels.items():
            v.close()
        self.channels = {}
        self.input_list = [self.server]
        self.connected = False

    def run(self):
        self.input_list = [self.server]
        self.channels = {}
        # run until stopEvent is set
        while not self.stopEvent.is_set():
            inputready, outputready, exceptready = select.select(self.input_list, [], [], 1)

            # if stopEvent is set, close all proxied connections 
            if self.stopEvent.is_set():
                log('TCPProxy.run[%s:%s]: changeEvent is set' % (self.hostport, self.target), )
                self.close_all()
                #for k, v in self.channels.items():
                #    v.close()
                #self.channels = {}
                #self.input_list = [self.server]
                continue

            # normal operation, process received data 
            for s in inputready:

                # New connection
                if s == self.server:
                    self.on_accept()
                    log('TCPProxy.run[%s:%s]: accepted' % (self.hostport, self.target), )
                    self.update({'status': 'connected'})
                    break

                # Incoming data to be forwarded
                try:
                    data = s.recv(4096)
                except OSError as e:
                    log('TCPProxy.run[%s:%s]: OSError %s' % (self.hostport, self.target, e), )
                    data = b''
                except ConnectionResetError as e:
                    log('TCPProxy.run[%s:%s]: ConnectionResetError %s' % (self.hostport, self.target, e), )
                    data = b''

                # No data means the connection is closed
                if len(data):
                    self.dataReceived += len(data)
                    self.messagesReceived += 1
                    self.update({'dataReceived': self.dataReceived, 'messagesReceived': self.messagesReceived})
                    self.channels[s].send(data)
                    log('TCPProxy.run[%s:%s]: sent %s' % (self.hostport, self.target, len(data), ), )
                    continue

                log('TCPProxy.run[%s:%s]: has disconnected' % (self.hostport, self.target, ), )
                try:
                    if s in self.channels:
                        for c in [s, self.channels[s]]:
                            self.input_list.remove(c)
                            self.update({'status': 'disconnected'})
                            c.close()
                            del self.channels[c]
                            self.connected = False
                except KeyError as e:
                    log('TCPProxy.run[:%s%s]: KeyError %s' % (self.hostport, self.target, e), )
                    log(traceback.format_exc(), )

        log('TCPProxy.run[%s:%s]: stopEvent is set' % (self.hostportport, self.target), )


    def on_accept(self):
        clientsock, clientaddr = self.server.accept()
        log('TCPProxy.on_accept[%s:%s] has connected %s targetport: %s' % (self.hostport, self.target, (clientaddr), self.targetport,), )
        # XXX check self.maxconnect
        if self.connected:
            log('TCPProxy.on_accept[%s:%s] already have open connection' % (self.hostport, clientaddr,), )
            clientsock.close()
            return
        if not self.target:
            log('TCPProxy.on_accept[%s:%s] has connected, but no target' % (self.hostport, clientaddr,), )
            clientsock.close()
            return
        set_keepalive(clientsock, after_idle_sec=4, interval_sec=1, max_fails=3)
        clientsock.settimeout(5)
        forward = Forward()
        # XXX this needs to be done asynchronously
        s = Forward().start(self.target, self.targetport)

        if s:
            log('TCPProxy.on_accept[%s:%s] proxied from %s' % (self.hostport, self.target, clientaddr, ), )
            self.input_list.append(clientsock)
            self.input_list.append(s)
            self.channels[clientsock] = s
            self.channels[s] = clientsock
            self.connected = True
        else:
            log("TCPProxy.on_accept[%s:%s] Can't establish connection with remote server." % (self.hostport, self.target), )
            log("TCPProxy.on_accept[%s:%s] Closing connection with client side %s" % (self.hostport, self.target, clientaddr), )
            clientsock.close()



class ImpinjTCPProxy(TCPProxy):
    def __init__(self, host='0.0.0.0', hostport=None, target=None, targetport=5084, stopEvent=None, changeEvent=None, proxyStatusQueue=None):
        super(ImpinjTCPProxy, self).__init__(host, hostport, target, targetport, stopEvent=stopEvent, changeEvent=changeEvent,
                                             proxyStatusQueue=proxyStatusQueue)


if __name__ == '__main__':

    stopEvent = Event()
    changeEvent = Event()

    targets = [
            None,
            '192.168.40.65',
            '192.168.40.62',
            '192.168.40.65',
            '192.168.40.62',
    ]

    #server = TCPProxy(host='0.0.0.0', hostport=5084, target='192.168.40.62', targetport=5084, stopEvent=stopEvent, changeEvent=changeEvent)
    server = ImpinjTCPProxy(target=None, stopEvent=stopEvent, changeEvent=changeEvent)

    def sigintHandler(signal, frame):
        if len(targets) > 0:
            target = targets.pop()
            log('SIGINT received %s target: %s' % (signal, target), )
            server.change(target, 5084)
        else:
            log('SIGINT received %s, setting stopEvent' % (signal,), )
            stopEvent.set()
            changeEvent.set()
  
    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    log('starting server', )
    server.start()
    log('server started, waiting', )
    stopEvent.wait()
    log('server stopping, joining', )
    server.join()
    log('server stopped', )




