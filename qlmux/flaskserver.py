import json
import sys
import asyncio
import argparse
import time
from datetime import timedelta
import datetime
import signal
import traceback
from threading import Thread, Event, Semaphore
from queue import Queue
from deepdiff import DeepDiff
# apt install python3-openssl
#from OpenSSL import SSL
import ssl
from werkzeug.serving import make_server
from flask import Flask, render_template, render_template_string, Response, request
import logging
from flask.logging import default_handler

from .htmlpage import TestPage
from .utils import log
from .printer import PrinterQueue
from .pythonproxy import ImpinjTCPProxy



class FlaskServer(Thread):
    #app1 = Flask(__name__)

    def root(self): 
        #testpage = TestPage.testpage
        testpage = TestPage()
        #log('%s' % testpage, )
        return str(testpage)

    # SSE endpoint to stream printer updates
    #@app1.route('/printerTitleClicked')
    def printerTitleClicked(self):
        log('printerTitleClicked: request: %s' % (request), )
        return 'OK'
    # SSE endpoint to stream printer updates
    #@app1.route('/printerTimeClicked')
    def printerTimeClicked(self):
        log('printerTimeClicked: request: %s' % (request), )
        self.printerResetEvent.set()
        self.printers = {}
        return 'OK'
    # SSE endpoint to stream impinj updates
    #@app1.route('/impinjTitleClicked')
    def impinjTitleClicked(self):
        log('impinjTitleClicked: request: %s' % (request), )
        return 'OK'
    # SSE endpoint to stream impinj updates
    #@app1.route('/impinjTimeClicked')
    def impinjTimeClicked(self):
        log('impinjTimeClicked: request: %s' % (request), )
        self.impinjResetEvent.set()
        self.impinjs = {}
        return 'OK'

    # SSE endpoint to stream printer updates
    #@app1.route('/title_updates')
    def title_updates(self):
        with self.semaphore:
            data = 'data: {}\n\n'.format(json.dumps({
                'lastUpdate': datetime.datetime.now().strftime('%H:%M:%S'),
                'replaceTable': True,
            }, ))
        log('title_updates: data: %s' % (data), )
        return Response(data, content_type='text/event-stream')

    # SSE endpoint to stream rfid reader updates
    #@app1.route('/impinj_updates')
    def impinj_updates(self):
        #if time.time() - self.lastImpinjsUpdate > 10:
        #    self.setImpinjResults()
        with self.semaphore:
            replaceTable = self.setImpinjResults()
            data = 'data: {}\n\n'.format(json.dumps({
                'results': self.impinjResults, 
                'lastUpdate': datetime.datetime.now().strftime('%H:%M:%S'),
                'replaceTable': replaceTable,
            }, ))

        log('impinj_updates: Response: %s' % (data) )
        return Response(data, content_type='text/event-stream')


    # SSE endpoint to stream printer updates
    #@app1.route('/printer_updates')
    def printer_updates(self):
        #if time.time() - self.lastPrintersUpdate > 10:
        #    self.setPrinterResults()
        with self.semaphore:
            replaceTable = self.setPrinterResults()
            data = 'data: {}\n\n'.format(json.dumps({
                'results': self.printerResults, 
                'lastUpdate': datetime.datetime.now().strftime('%H:%M:%S'),
                'replaceTable': replaceTable,
            }, ))

        log('printer_updates: Response: %s' %(data), )
        return Response(data, content_type='text/event-stream')

    # Route to handle impinj clicks
    def impinjClicked(self):
        try:
            data = request.get_json()
        except NameError:
            log('impinjClicked: no request', )
            log('impinjClicked: request: %s' % (request), ) 
            return 'OK'

        #log('impinjClicked clicked: request: %s' % (request), ) 
        impinj_name = data.get('impinj_name')
        #log('impinjClicked[%s] AAAAA' % (impinj_name), )
        #log('data:', data, )
        # Handle the click event here
        # For example, you could trigger some action or return a response to the client
        return 'OK'

    def printerClicked(self):
        try:
            data = request.get_json()
        except NameError:
            log('Printer clicked: no request', )
            log('Printer clicked: request: %s' % (request), ) 
            return 'OK'

        #log('Printer clicked: request: %s' % (request), ) 
        printer_name = data.get('printer_name')
        log('printerClicked[%s] request: %s' % (printer_name, request), )
        #log('data:', data, )
        # Handle the click event here
        # For example, you could trigger some action or return a response to the client
        return 'OK'

    # Route to update printer queue
    def updatePrinterQueue(self):
        try:
            data = request.get_json()
        except NameError:
            log('FlaskServer.updatePrinterQueue: Printer clicked: no request', ) 
            log('FlaskServer.updatePrinterQueue: Update printer status: request: %s' % (request), )
            return 'OK'
        log('FlaskServer.updatePrinterQueue: data: %s' % data, )
        queue = data['queue']
        id = data['id']
        queue = data['queue']
        log('FlaskServer.updatePrinterQueue[%s] queue: %s AAAA' % (id, queue), )
        #for k in ['left', 'center', 'right', 'disabled']:
        #    self.printers[id][k] = False
        self.printers[id]['queue'] = queue
        if queue:
            self.qlmuxd.setPrinterQueue(id, PrinterQueue[queue.upper()])
        else:
            self.qlmuxd.setPrinterQueue(id, PrinterQueue.DISABLED)
        #self.setPrinterResults()
        log('FlaskServer.updatePrinterQueue: %s, queue: %s' % (id, queue, ), )
        return 'OK'

    # Route to update printer status
    def updatePrinterStatus(self):
        try:
            data = request.get_json()
        except NameError:
            log('FlaskServer.updatePrinterStatus: Printer clicked: no request', ) 
            log('FlaskServer.updatePrinterStatus: Update printer status: request: %s' % (request), )
            return 'OK'
        log('FlaskServer.updatePrinterStatus: data: %s' % data, )
        queue = data['queue'].lower()
        id = data['id']
        enabled = data['enabled']
        log('FlaskServer.updatePrinterStatus[%s] enabled: %s AAAA' % (id, enabled), )
        #for k in ['left', 'center', 'right']:
        #    self.printers[id][k] = False
        self.printers[id][queue] = enabled
        self.printers[id]['queue'] = queue
        log('FlaskServer.updatePrinterStatus[%s] %s' % (id, self.printers[id]), )
        if enabled:
            self.qlmuxd.setPrinterQueue(id, PrinterQueue[queue.upper()])
        else:
            self.qlmuxd.setPrinterQueue(id, PrinterQueue.DISABLED)
        #self.setPrinterResults()
        #log('FlaskServer.updatePrinterStatus: %s, queue: %s enabled: %s' % (id, queue, enabled), )
        return 'OK'


    # Set the listen address for an Impinj reader, if the address is already in use, assign a new one
    # to the existing reader
    def setImpinjListenAddress(self, id, proxyPort):
        listening = { v['proxyPort']: k for k, v in self.impinjs.items() }
        log('FlaskServer.setImpinjListenAddress[%s]: listening: %s' % (id, listening), )
        for k, v in self.impinjs.items():
            if v['proxyPort'] == proxyPort:
                v['proxyPort'] = 'Disabled'
        listening = { v['proxyPort']: k for k, v in self.impinjs.items() }
        log('FlaskServer.setImpinjListenAddress[%s]: listening: %s' % (id, listening), )
        if proxyPort in listening:
            k = listening.pop(proxyPort)
            available = [ '127.0.0.%d' % i for i in range(1,4) if i not in listening ]  
            self.impinjs[k]['proxyPort'] = available[0] if available else 'Disabled'
            log('FlaskServer.setImpinjListenAddress[%s]: proxyPort: %s already in use, assigning %s' % (id, proxyPort, self.impinjs[k]['proxyPort']), )
        self.impinjs[id]['proxyPort'] = proxyPort
        log('FlaskServer.setImpinjListenAddress[%s]: proxyPort: %s' % (id, proxyPort), )

    def updateImpinjStatus(self):
        try:
            data = request.get_json()
        except NameError:
            log('FlaskSEver.updateImpinjStatus: Impinj clicked: no request', ) 
            log('FlaskSEver.updateImpinjStatus: Update Impinj status: request: %s' % (request), )
            return 'OK'
        id = data['id']
        proxyPort = data['proxyPort']
        log('FlaskServer.updateImpinjStatus[%s]: proxyPort: %s' % (id, proxyPort), )
        self.setImpinjListenAddress(id, proxyPort)
        # XXX probably need to create/destroy the ImpinjTCPProxy's here


        #log('FlaskServer.updateImpinjStatus[%s] enabled: %s' % (id, enabled), )
        #log('FlaskServer.updateImpinjStatus[%s] %s' % (id, self.impinjs[id]), )
        #if self.impinjTCPProxy:
        #    self.impinjTCPProxy.change(target=self.impinjs[id]['hostaddr'] if enabled else None)
        return 'OK'

    def __init__(self, changeEvent=None, printerResetEvent=None, impinjResetEvent=None,
                 impinjTCPProxy=None, qlmuxd=None, **kwargs):
        # XXX need to instantiate the ImpinjTCPProxy later for the individual RFID readers
        #self.impinjTCPProxy = impinjTCPProxy
        self.printerResetEvent = printerResetEvent
        self.impinjResetEvent = impinjResetEvent
        self.changeEvent = changeEvent
        self.qlmuxd = qlmuxd
        self.semaphore = Semaphore()
        self.app1 = Flask(__name__)
        #self.app1.logger.removeHandler(default_handler)
        #self.app1.logger.setLevel(logging.ERROR)
        #self.app1.logger.error('FlaskServer: __init__: AAAAA')

        # this gets rid of the werkzeug logging which defaults to logging GET requests
        wlog = logging.getLogger('werkzeug')
        wlog.setLevel(logging.ERROR)

        self.app1.add_url_rule('/', 'root', self.root)
        self.app1.add_url_rule('/title_updates', 'title_updates', self.title_updates)
        self.app1.add_url_rule('/impinj_updates', 'impinj_updates', self.impinj_updates)
        self.app1.add_url_rule('/printer_updates', 'printer_updates', self.printer_updates)
        self.app1.add_url_rule('/printerClicked', 'printerClicked', self.printerClicked, methods=['POST'])
        self.app1.add_url_rule('/impinjClicked', 'impinjClicked', self.impinjClicked, methods=['POST'])
        self.app1.add_url_rule('/updateImpinjStatus', 'updateImpinjStatus', self.updateImpinjStatus, methods=['POST'])
        self.app1.add_url_rule('/updatePrinterStatus', 'updatePrinterStatus', self.updatePrinterStatus, methods=['POST'])
        self.app1.add_url_rule('/updatePrinterQueue', 'updatePrinterQueue', self.updatePrinterQueue, methods=['POST'])

        self.app1.add_url_rule('/printerTitleClicked', 'printerTitleClicked', self.printerTitleClicked, methods=['POST'])
        self.app1.add_url_rule('/printerTimeClicked', 'printerTimeClicked', self.printerTimeClicked, methods=['POST'])
        self.app1.add_url_rule('/impinjTitleClicked', 'impinjTitleClicked', self.impinjTitleClicked, methods=['POST'])
        self.app1.add_url_rule('/impinjTimeClicked', 'impinjTimeClicked', self.impinjTimeClicked, methods=['POST'])

        super(FlaskServer, self).__init__()
        #self.semaphore = Semaphore()
        self.impinjResults = []
        self.printerResults = []

        self.impinjs = {}
        self.printers = {}
        self.lastPrintersUpdate = time.time()
        self.lastImpinjsUpdate = time.time()
        self.app = self.app1
        if False:
            #CERT_FILE = 'whiskey.local+5.pem' 
            #KEY_FILE = 'whiskey.local+5-key.pem'
            CERT_FILE = 'wg.wimsey.co.pem' 
            KEY_FILE = 'wg.wimsey.co-key.pem'
            #CERT_FILE = 'whiskey.ip.pem' 
            #KEY_FILE =  'whiskey.ip-key.pem'
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            try:
                context.load_cert_chain(CERT_FILE, KEY_FILE)
            except Exception as e:
                log('FlaskServer: __init__: Error loading certificate: %s' % e, )
                log(traceback.format_exc(), )
                exit(0)

            self.server = make_server('0.0.0.0', 9143, self.app, ssl_context=context)
            log('FlaskServer: __init__: using SSL', )
        else:
            self.server = make_server('0.0.0.0', 9180, self.app)
            log('FlaskServer: __init__: not using SSL', )
        self.ctx = self.app.app_context()
        self.ctx.push()

    def sysUpTime(self, sysuptime):
            days, remainder = divmod(int(sysuptime)/100, 86400)
            if days:
                return "%2.1f days" % ( days + remainder/86400)
            else:
                hours, remainder = divmod(remainder, 3600)
                minutes, seconds = divmod(remainder, 60)
                return '%02d:%02d:%02d' % (hours, minutes, seconds)


    def setImpinjResults(self):
        # create the impinjResults list
        self.newImpinjResults = []
        self.lastImpinjsUpdate = time.time()
        for i, (impinj, info) in enumerate(self.impinjs.items()):
            #log('FlaskServer.setImpinjResults[%d:%s]: info %s ' % (i, impinj, info), )
            hostname = info.get('hostname', None)
            hostaddr = info.get('hostaddr', None)
            macaddr = info.get('MACAddress', None)
            serialnumber = info.get('SerialNumber', None)
            address = f"<a href='http://{hostaddr}'>{hostaddr}</a>" if hostaddr else 'n/a'
            tooltip0 = f"{info.get('Model','')} {info.get('sysdescr','')}"

            seenElapsed = time.time() - info.get('lastSeen', 0)
            #if seenElapsed > 10:
            #    log('FlaskServer.setImpinjResults[%d:%s]: seenElapsed: %s' % (i, impinj, seenElapsed), )
            lastSeen = datetime.datetime.utcfromtimestamp(seenElapsed).strftime('%H:%M:%S') if seenElapsed > 10 else '< 10s'
            sysUpTime = self.sysUpTime(info.get('SysUpTime', 0))
            self.newImpinjResults.append({
                'id': impinj,
                'name': hostname, 
                'address': info.get('hostaddr',''),
                'tooltip0': tooltip0,
                'status': info.get('Status',''),
                'media': info.get('Media',''),
                'enabled': info.get('enabled', False),
                'proxyPort': info.get('proxyPort', 'Disabled'),
                'SysUpTime': sysUpTime,
                'lastSeen': lastSeen,
                'lastSeenUpTime': '%s / %s' % (lastSeen, sysUpTime),
                })

        diff = DeepDiff(self.impinjResults, self.newImpinjResults)
        if len(diff):
            log('FlaskServer.setImpinjResults: diff: %s' % diff, )
            log('FlaskServer.setImpinjResults: results: %s' % self.impinjResults, )
            self.impinjResults = self.newImpinjResults
            return True
        log('FlaskServer.setImpinjResults: no change', )
        log('FlaskServer.setImpinjResults: results: %s' % self.impinjResults, )
        return False

    # called by the main thread to update
    def impinjUpdate(self, impinjInfo=None):
        # update the impinjs dictionary
        #log('FlaskServer.impinjUpdate: impinjInfo: %s' % impinjInfo, )
        listenAddresses = ['127.0.0.%d' % i for i in range(1,4)] + ['Disabled',]
        with self.semaphore:
            for i, (impinj, info) in enumerate(impinjInfo.items()):
                if impinj not in self.impinjs:
                    listening = { v['proxyPort']: k for k, v in self.impinjs.items() }
                    log('FlaskServer.impinjUpdate: listening: %s' % listening, )
                    impinjs = len(self.impinjs)
                    addresses = len(listenAddresses)
                    index = impinjs if impinjs < addresses else addresses - 1
                    self.impinjs[impinj] = {'proxyPort': listenAddresses[index],}
                    hostname = info.get('hostname', None).lower()
                    log('FlaskServer.impinjUpdate[%d:%s]: impinj %s hostname: %s table: %s kiosk: %s' % 
                        (i, impinj, self.impinjs[impinj], hostname, hostname.endswith('table'), hostname.endswith('kiosk')), )
                    if hostname.endswith('table') and '127.0.0.1' not in listening:
                        log('FlaskServer.impinjUpdate[%d:%s]: impinj %s 127.0.0.1 for TABLE' % (i, impinj, self.impinjs[impinj]), )
                        self.impinjs[impinj] = {'proxyPort': '127.0.0.1', }
                        continue
                    if hostname.endswith('kiosk') and '127.0.0.2' not in listening:
                        log('FlaskServer.impinjUpdate[%d:%s]: impinj %s 127.0.0.2 for KIOSK' % (i, impinj, self.impinjs[impinj]), )
                        self.impinjs[impinj] = {'proxyPort': '127.0.0.2', }
                        continue
                    if '127.0.0.1' not in listening:
                        log('FlaskServer.impinjUpdate[%d:%s]: impinj %s 127.0.0.1' % (i, impinj, self.impinjs[impinj]), )
                        self.impinjs[impinj] = {'proxyPort': '127.0.0.1'}
                        continue
                    if '127.0.0.2' not in listening:
                        log('FlaskServer.update[%d:%s]: impinj %s 127.0.0.2' % (i, impinj, self.impinjs[impinj]), )
                        self.impinjs[impinj] = {'proxyPort': '127.0.0.2'}
                        continue
                    log('FlaskServer.update[%d:%s]: impinj %s Disabled' % (i, impinj, self.impinjs[impinj]), )
                    self.impinjs[impinj] = {'proxyPort': 'Disabled'}

                self.impinjs[impinj]['lastSeen'] = time.time()
                if info:
                    for j, (k, v) in enumerate(info.items()):
                        #log('FlaskServer.update[%d:%d:%s]: k: %s, v: %s' % (i, j, impinj, k, v), )
                        self.impinjs[impinj][k] = v
                        #print('FlaskServer.update[%d:%d:%s]: impinj %s' % (i, j, impinj, self.impinjs[impinj]), )
        
        #log('FlaskServer.impinjUpdate: impinjs: %s' % self.impinjs, )
        #self.setImpinjResults()

    def setPrinterResults(self):
        self.newPrinterResults = []
        self.lastPrintersUpdate = time.time()
        printerStats = self.qlmuxd.printerStats()
        #log('FlaskServer.setPrinterResults: printerStats: %s' % printerStats, )
        for i, (printerId, info) in enumerate(self.printers.items()):
            log('FlaskServer.setPrinterResults[%d:%s]: info %s' % (i, printerId, info), )
            hostaddr = info.get('hostaddr', None)
            hostname = info.get('hostname', None)
            macaddr = info.get('MACAddress', None)
            serialnumber = info.get('SerialNumber', None)
            address = f"<a href='http://{hostaddr}'>{hostaddr}</a>" if hostaddr else 'n/a'
            tooltip0 = f"{info.get('Model','')} {info.get('sysdescr','')}"
            seenElapsed = time.time() - info.get('lastSeen', 0)
            stats = printerStats.get(printerId, None)
            #if seenElapsed > 10:
            #    log('FlaskServer.setPrinterResults[%d:%s]: seenElapsed: %s' % (i, printerId, seenElapsed), )
            lastSeen = datetime.datetime.utcfromtimestamp(seenElapsed).strftime('%H:%M:%S') if seenElapsed > 10 else '< 10s'
            sysUpTime = self.sysUpTime(info.get('SysUpTime', 0))
            self.newPrinterResults.append({
                'id': printerId,
                'name': hostname, 
                'address': info.get('hostaddr',''),
                'tooltip0': tooltip0,
                'status': info.get('Status',''),
                'media': info.get('Media',''),
                #'left': info.get('left', False),
                #'center': info.get('center', False),
                #'right': info.get('right', False),
                'queue': info.get('queue', 'Center'),
                'stats': '%s/%s' % (stats[0], stats[1]) if stats else 'n/a',
                'SysUpTime': sysUpTime,
                'lastSeen': lastSeen,
                'lastSeenUpTime': '%s / %s' % (lastSeen, sysUpTime),
                }
            )
        diff = DeepDiff(self.printerResults, self.newPrinterResults)
        if len(diff):
            log('FlaskServer.setPrinterResults: diff: %s' % diff, )
            self.printerResults = self.newPrinterResults
            return True
        log('FlaskServer.setPrinterResults: no change', )
        return False
        #log('FlaskServer.printerUpdate: results: %s' % self.printerResults, )

    def printerUpdate(self, printerInfo=None):
        #log('FlaskServer.update: printerInfo: %s' % printerInfo, )
        with self.semaphore:
            for i, (printer, info) in enumerate(printerInfo.items()):
                macaddr = info.get('MACAddress', None)
                serialnumber = info.get('SerialNumber', None)
                if printer not in self.printers:
                    self.printers[printer] = {'queue': 'center', }
                    #log('FlaskServer.update[%d:%s]: printer %s EMPTY' % (i, printer, self.printers[printer]), )
                self.printers[printer]['lastSeen'] = time.time()
                if info:
                    for j, (k, v) in enumerate(info.items()):
                        if v != '':
                            self.printers[printer][k] = v

        #self.setPrinterResults()

    def run(self):
        log('FlaskSever.run: Starting server', )
        self.server.serve_forever()
        log('FlaskSever.run: server started', )

    def shutdown(self):
        log('FlaskSever.Stopping server', )
        self.server.shutdown()
        self.server.server_close()
        self.ctx.pop()

def main():

    sigintEvent = Event()
    changeEvent = Event()
    stopEvent = Event()
    sigintEvent.clear()
    changeEvent.clear()
    stopEvent.clear()

    def sigintHandler(signal, frame):
        log('SIGINT received %s' % (signal,), )
        sigintEvent.set()
        changeEvent.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    server = FlaskServer()
    server.start()

    while changeEvent.wait():
        changeEvent.clear()
        if sigintEvent.is_set():
            stopEvent.set()
            log('Shutting down server', )
            server.shutdown()
            log('Server shutdown', )
            break

if __name__ == '__main__':

    main()

