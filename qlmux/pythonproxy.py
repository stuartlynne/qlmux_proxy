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

class Forward:
    def __init__(self):
        self.forward = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        set(self.forward, after_idle_sec=4, interval_sec=1, max_fails=3)
        self.forward.settimeout(5)

    def start(self, host, port):
        try:
            self.forward.connect((host, port))
            return self.forward
        except Exception as e:
            print(e, file=sys.stderr)
            return None

class TCPProxy(Thread):

    def __init__(self, host=None, hostport=None, target=None, targetport=None, stopEvent=None, changeEvent=None, tcpStatusQueue=None):
        super(TCPProxy, self).__init__()
        self.input_list = []
        self.channel = {}
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        set_keepalive(self.server, after_idle_sec=4, interval_sec=1, max_fails=3)
        self.server.settimeout(5)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, hostport))
        self.server.listen(200)
        self.host = host
        self.hostport = hostport
        self.target = target
        self.targetport = targetport
        self.stopEvent = stopEvent
        self.changeEvent = changeEvent
        self.tcpStatusQueue = tcpStatusQueue
        print('TCPProxy.__init__[%s] target: %s targetport: %s' % (self.host, self.target, self.targetport), file=sys.stderr)

        self.dataReceived = 0
        self.messagesReceived = 0

    def update(self, tcpStatus):
        print('TCPProxy.update[%s] %s' % (self.target, tcpStatus,), file=sys.stderr)
        if self.tcpStatusQueue:
            self.tcpStatusQueue.put({self.target: tcpStatus})

    # Change the target of the proxy, 
    #      - close existing connections
    #      - set the new target    
    #      - set changeEvent to signal the change
    def change(self, target, targetport=None):
        print('TCPProxy.change[%s] target: %s targetport: %s)' % (self.host, target, targetport), file=sys.stderr)
        self.update({'status': 'closing'})
        self.target = target
        if targetport:
            self.targetport = targetport
        print('TCPProxy.change[%s] target: %s targetport: %s' % (self.host, self.target, self.targetport), file=sys.stderr)
        self.dataReceived = 0
        self.messagesReceived = 0
        #for k, v in self.channel.items():
        #    v.close()
        #self.channel = {}
        self.changeEvent.set()

    def run(self):
        self.input_list = [self.server]
        self.channels = {}
        # run until stopEvent is set
        while not self.stopEvent.is_set():
            inputready, outputready, exceptready = select.select(self.input_list, [], [], 1)

            # if changeEvent is set, close all proxied connections 
            if self.changeEvent.is_set():
                print('TCPProxy.run: changeEvent is set', file=sys.stderr)
                self.changeEvent.clear()
                for k, v in self.channels.items():
                    v.close()
                self.channels = {}
                self.input_list = [self.server]
                continue

            # normal operation, process received data 
            for s in inputready:

                print('TCPProxy.run: AAAA', file=sys.stderr)

                # New connection
                if s == self.server:
                    print('TCPProxy.run: BBBB', file=sys.stderr)
                    self.on_accept()
                    print('TCPProxy.run: CCCC', file=sys.stderr)
                    self.update({'status': 'connected'})
                    break
                print('TCPProxy.run: DDDD', file=sys.stderr)

                # Incoming data to be forwarded
                try:
                    data = s.recv(4096)
                except ConnectionResetError as e:
                    print('TCPProxy.run: %s ConnectionResetError %s' % (s.getpeername(), e), file=sys.stderr)
                    data = b''

                # No data means the connection is closed
                if len(data):
                    self.dataReceived += len(data)
                    self.messagesReceived += 1
                    self.update({'dataReceived': self.dataReceived, 'messagesReceived': self.messagesReceived})
                    self.channels[s].send(data)
                    continue

                print('TCPProxy.run[%s]: %s has disconnected' % (self.host, s.getpeername(),), file=sys.stderr)
                for c in [s, self.channels[s]]:
                    self.input_list.remove(c)
                    self.update({'status': 'disconnected'})
                    c.close()
                    del self.channels[c]

        print('TCPProxy.run: stopEvent is set', file=sys.stderr)


    def on_accept(self):
        print('TCPProxy.on_accept[%s] 1111' % (self.host,), file=sys.stderr)
        clientsock, clientaddr = self.server.accept()
        print('TCPProxy.on_accept[%s] 2222' % (self.host,), file=sys.stderr)
        print('TCPProxy.on_accept[%s] has connected %s target: %s targetport: %s' % (self.host, (clientaddr), self.target, self.targetport,), file=sys.stderr)
        print('TCPProxy.on_accept[%s] 3333' % (self.host,), file=sys.stderr)
        if not self.target:
            print('TCPProxy.on_accept[%s] has connected, but no target' % (clientaddr,), file=sys.stderr)
            clientsock.close()
            return
        set_keepalive(clientsock, after_idle_sec=4, interval_sec=1, max_fails=3)
        clientsock.settimeout(5)
        print('TCPProxy.on_accept[%s] 4444' % (self.host,), file=sys.stderr)
        forward = Forward()
        print('TCPProxy.on_accept[%s] 5555' % (self.host,), file=sys.stderr)
        # XXX this needs to be done asynchronously
        s = Forward().start(self.target, self.targetport)
        print('TCPProxy.on_accept[%s] 6666' % (self.host,), file=sys.stderr)

        if s:
            print('TCPProxy.on_accept: %s proxied to %s' % (clientaddr, (self.target, self.targetport)), file=sys.stderr)
            print(clientaddr, "has connected", file=sys.stderr)
            self.input_list.append(clientsock)
            self.input_list.append(s)
            self.channels[clientsock] = s
            self.channels[s] = clientsock
        else:
            print("Can't establish connection with remote server.", file=sys.stderr)
            print("Closing connection with client side", clientaddr, file=sys.stderr)
            clientsock.close()

class ImpinjTCPProxy(TCPProxy):

    def __init__(self, host='0.0.0.0', hostport=5084, target=None, targetport=5084, stopEvent=None, changeEvent=None):
        super(ImpinjTCPProxy, self).__init__(host, hostport, target, targetport, stopEvent=stopEvent, changeEvent=changeEvent)


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
            print('SIGINT received %s target: %s' % (signal, target), file=sys.stderr)
            server.change(target, 5084)
        else:
            print('SIGINT received %s, setting stopEvent' % (signal,), file=sys.stderr)
            stopEvent.set()
            changeEvent.set()
  
    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    print('starting server', file=sys.stderr)
    server.start()
    print('server started, waiting', file=sys.stderr)
    stopEvent.wait()
    print('server stopping, joining', file=sys.stderr)
    server.join()
    print('server stopped', file=sys.stderr)




