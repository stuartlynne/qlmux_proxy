import json
import sys
import asyncio
import argparse
import time
from datetime import timedelta
import datetime
import signal
from threading import Thread, Event, Semaphore
from queue import Queue
from werkzeug.serving import make_server
from flask import Flask, render_template, render_template_string, Response, request
import logging
from flask.logging import default_handler

from .htmlpage import TestPage
from .utils import log
from .printer import PrinterQueue



class FlaskServer(Thread):
    #app1 = Flask(__name__)

    def root(self): 
        #testpage = TestPage.testpage
        testpage = TestPage()
        #log('%s' % testpage, )
        return str(testpage)

    # SSE endpoint to stream printer updates
    #@app1.route('/printer_updates')
    def impinj_updates(self):
        if time.time() - self.lastImpinjsUpdate > 10:
            self.setImpinjResults()
        with self.semaphore:
            data = 'data: {}\n\n'.format(json.dumps({
                'header': self.impinjHeader, 
                'results': self.impinjResults, 
                'lastUpdate': datetime.datetime.now().strftime('%H:%M:%S'),
            }, ))

        #log('impinj_updates:', data, )
        return Response(data, content_type='text/event-stream')


    # SSE endpoint to stream printer updates
    #@app1.route('/printer_updates')
    def printer_updates(self):
        if time.time() - self.lastPrintersUpdate > 10:
            self.setPrinterResults()
        with self.semaphore:
            data = 'data: {}\n\n'.format(json.dumps({
                'header': self.printerHeader, 
                'results': self.printerResults, 
                'lastUpdate': datetime.datetime.now().strftime('%H:%M:%S'),
            }, ))

        #log('printer_updates:', data, )
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
        #log('printerClicked[%s]' % (printer_name), )
        #log('data:', data, )
        # Handle the click event here
        # For example, you could trigger some action or return a response to the client
        return 'OK'

    # Route to update printer status
    def updatePrinterStatus(self):
        try:
            data = request.get_json()
        except NameError:
            log('FlaskServer.updatePrinterStatus: Printer clicked: no request', ) 
            log('FlaskServer.updatePrinterStatus: Update printer status: request: %s' % (request), )
            return 'OK'
        queue = data['queue']
        id = data['id']
        enabled = data['enabled']
        #log('FlaskServer.updatePrinterStatus[%s] enabled: %s AAAA' % (id, enabled), )
        for k in ['left', 'center', 'right']:
            self.printers[id][k] = False
        self.printers[id][queue] = enabled
        if enabled:
            self.qlmuxd.setPrinterQueue(id, PrinterQueue[queue.upper()])
        else:
            self.qlmuxd.setPrinterQueue(id, PrinterQueue.DISABLED)
        self.setPrinterResults()
        #log('FlaskServer.updatePrinterStatus: %s, queue: %s enabled: %s' % (id, queue, enabled), )
        return 'OK'

    def updateImpinjStatus(self):
        try:
            data = request.get_json()
        except NameError:
            log('FlaskSEver.updateImpinjStatus: Impinj clicked: no request', ) 
            log('FlaskSEver.updateImpinjStatus: Update Impinj status: request: %s' % (request), )
            return 'OK'
        id = data['id']
        enabled = data['enabled']
        log('updateImpinjStatus[%s]: enabled: %s AAAAA' % (id, enabled), )
        for k, v in self.impinjs.items():
            self.impinjs[k]['enabled'] = False
        self.impinjs[id]['enabled'] = enabled
        self.setImpinjResults()
        #log('FlaskServer.updateImpinjStatus[%s] enabled: %s' % (id, enabled), )
        #log('FlaskServer.updateImpinjStatus[%s] %s' % (id, self.impinjs[id]), )
        if self.impinjTCPProxy:
            self.impinjTCPProxy.change(target=self.impinjs[id]['hostaddr'], )
        return 'OK'

    def __init__(self, impinjTCPProxy=None, qlmuxd=None, **kwargs):
        self.impinjTCPProxy = impinjTCPProxy
        self.qlmuxd = qlmuxd
        self.semaphore = Semaphore()
        self.app1 = Flask(__name__)
        #self.app1.logger.removeHandler(default_handler)
        #self.app1.logger.setLevel(logging.ERROR)
        #self.app1.logger.error('FlaskServer: __init__: AAAAA')

        # this gets rid of the werkzeug logging which defaults to logging GET requests
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        self.app1.add_url_rule('/', 'root', self.root)
        self.app1.add_url_rule('/impinj_updates', 'impinj_updates', self.impinj_updates)
        self.app1.add_url_rule('/printer_updates', 'printer_updates', self.printer_updates)
        self.app1.add_url_rule('/printerClicked', 'printerClicked', self.printerClicked, methods=['POST'])
        self.app1.add_url_rule('/impinjClicked', 'impinjClicked', self.impinjClicked, methods=['POST'])
        self.app1.add_url_rule('/updateImpinjStatus', 'updateImpinjStatus', self.updateImpinjStatus, methods=['POST'])
        self.app1.add_url_rule('/updatePrinterStatus', 'updatePrinterStatus', self.updatePrinterStatus, methods=['POST'])
        super(FlaskServer, self).__init__()
        #self.semaphore = Semaphore()
        self.impinjResults = []
        self.printerResults = []
            #{ 'name': 'Printer 1', 'status': 'Online', 'media': 'Room 101', 'enabled': True },
            #{ 'name': 'Printer 2', 'status': 'Offline', 'media': 'Room 102', 'enabled': False },
            #{ 'name': 'Printer 3', 'status': 'Offline', 'media': 'Room 103', 'enabled': True },
            #{ 'name': 'Printer 1', 'status': 'Online', 'media': 'Room 101', 'enabled': True },
            #{ 'name': 'Printer 2', 'status': 'Offline', 'media': 'Room X102', 'enabled': False },
            #{ 'name': 'Time', 'status': 'Last Update', 'media': f'{time.time()}', 'enabled': True },

        self.impinjs = {}
        self.printers = {}
        self.lastPrintersUpdate = time.time()
        self.lastImpinjsUpdate = time.time()
        self.impinjHeader = ['Name', 'Address', '', 'UpTime', 'Enabled', 'Last Seen', ]
        self.printerHeader = ['Name', 'Address', 'Status', 'Media', 'UpTime', 'Left', 'Center', 'Right', 'Stats', 'Last Seen',]
        self.app = self.app1
        self.server = make_server('0.0.0.0', 5000, self.app)
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
        self.impinjResults = []
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
            self.impinjResults.append({
                'id': impinj,
                'name': hostname, 
                'address': info.get('hostaddr',''),
                'tooltip0': tooltip0,
                'status': info.get('Status',''),
                'media': info.get('Media',''),
                'enabled': info.get('enabled', False),
                'SysUpTime': self.sysUpTime(info.get('SysUpTime', 0)),
                'lastSeen': datetime.datetime.utcfromtimestamp(seenElapsed).strftime('%H:%M:%S') if seenElapsed > 10 else '< 10s',
                })

        #log('FlaskServer.setImpinjResults: results: %s' % self.impinjResults, )

    # called by the main thread to update
    def impinjUpdate(self, impinjInfo=None):
        # update the impinjs dictionary
        #log('FlaskServer.impinjUpdate: impinjInfo: %s' % impinjInfo, )
        with self.semaphore:
            for i, (impinj, info) in enumerate(impinjInfo.items()):
                if impinj not in self.impinjs:
                    self.impinjs[impinj] = {}
                    if len(self.impinjs) == 1:
                        self.impinjs[impinj] = {'enabled': True, }
                        self.impinjTCPProxy.change(target=info.get('hostaddr', None), )
                        #log('FlaskServer.update[%d:%s]: impinj %s EMPTY' % (i, impinj, self.impinjs[impinj]), )
                self.impinjs[impinj]['lastSeen'] = time.time()
                if info:
                    for j, (k, v) in enumerate(info.items()):
                        #log('FlaskServer.update[%d:%d:%s]: k: %s, v: %s' % (i, j, impinj, k, v), )
                        self.impinjs[impinj][k] = v
                        #print('FlaskServer.update[%d:%d:%s]: impinj %s' % (i, j, impinj, self.impinjs[impinj]), )
        
        #log('FlaskServer.impinjUpdate: impinjs: %s' % self.impinjs, )
        self.setImpinjResults()

    def setPrinterResults(self):
        self.printerResults = []
        self.lastPrintersUpdate = time.time()
        printerStats = self.qlmuxd.printerStats()
        #log('FlaskServer.setPrinterResults: printerStats: %s' % printerStats, )
        for i, (printerId, info) in enumerate(self.printers.items()):
            #log('FlaskServer.setPrinterResults[%d:%s]: info %s' % (i, printerId, info), )
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
            self.printerResults.append({
                'id': printerId,
                'name': hostname, 
                'address': info.get('hostaddr',''),
                'tooltip0': tooltip0,
                'status': info.get('Status',''),
                'media': info.get('Media',''),
                'left': info.get('left', False),
                'center': info.get('center', False),
                'right': info.get('right', False),
                'stats': '%s/%s' % (stats[0], stats[1]) if stats else 'n/a',
                'SysUpTime': self.sysUpTime(info.get('SysUpTime', 0)),
                'lastSeen': datetime.datetime.utcfromtimestamp(seenElapsed).strftime('%H:%M:%S') if seenElapsed > 10 else '< 10s',
                }
            )
        #log('FlaskServer.printerUpdate: results: %s' % self.printerResults, )

    def printerUpdate(self, printerInfo=None):
        #log('FlaskServer.update: vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv', )
        #log('FlaskServer.update: printerInfo: %s' % printerInfo, )
        with self.semaphore:
            for i, (printer, info) in enumerate(printerInfo.items()):
                macaddr = info.get('MACAddress', None)
                serialnumber = info.get('SerialNumber', None)
                if printer not in self.printers:
                    self.printers[printer] = {'left': False, 'center': True, 'right': False, }
                    #log('FlaskServer.update[%d:%s]: printer %s EMPTY' % (i, printer, self.printers[printer]), )
                self.printers[printer]['lastSeen'] = time.time()
                if info:
                    for j, (k, v) in enumerate(info.items()):
                        self.printers[printer][k] = v
        #log('FlaskServer.update: --------------------------------------------', )
        #log('FlaskServer.update: printers: %s' % self.printers, )
        #for i, (k, v) in enumerate(self.printers.items()):
        #    log('FlaskServer.update[%d]: printer %s: %s' % (i, k, v), )
        #log('FlaskServer.update: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^', )
        #for i, (k, v) in enumerate(self.printers.items()):
        #    log('FlaskServer.update[%d:%s] %s' % (i, k, v), )

        self.setPrinterResults()

    def run(self):
        log('run: Starting server', )
        self.server.serve_forever()
        log('run: server started', )

    def shutdown(self):
        log('Stopping server', )
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

