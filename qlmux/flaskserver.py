from flask import Flask, render_template, render_template_string, Response, request
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

from .htmlpage import TestPage



class FlaskServer(Thread):
    #app1 = Flask(__name__)

    def root(self): 
        #testpage = TestPage.testpage
        testpage = TestPage()
        print('%s' % testpage, file=sys.stderr)
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

        #print('impinj_updates:', data, file=sys.stderr)
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

        #print('printer_updates:', data, file=sys.stderr)
        return Response(data, content_type='text/event-stream')

    # Route to handle impinj clicks
    def impinjClicked(self):
        try:
            data = request.get_json()
        except NameError:
            print('impinjClicked: no request', file=sys.stderr)
            print('impinjClicked: request: %s' % (request), file=sys.stderr) 
            return 'OK'

        #print('impinjClicked clicked: request: %s' % (request), file=sys.stderr) 
        impinj_name = data.get('impinj_name')
        print('impinjClicked[%s] AAAAA' % (impinj_name), file=sys.stderr)
        #print('data:', data, file=sys.stderr)
        # Handle the click event here
        # For example, you could trigger some action or return a response to the client
        return 'OK'

    def printerClicked(self):
        try:
            data = request.get_json()
        except NameError:
            print('Printer clicked: no request', file=sys.stderr)
            print('Printer clicked: request: %s' % (request), file=sys.stderr) 
            return 'OK'

        #print('Printer clicked: request: %s' % (request), file=sys.stderr) 
        printer_name = data.get('printer_name')
        print('printerClicked[%s]' % (printer_name), file=sys.stderr)
        print('data:', data, file=sys.stderr)
        # Handle the click event here
        # For example, you could trigger some action or return a response to the client
        return 'OK'

    # Route to update printer status
    def updatePrinterStatus(self):
        try:
            data = request.get_json()
        except NameError:
            print('FlaskServer.updatePrinterStatus: Printer clicked: no request', file=sys.stderr) 
            print('FlaskServer.updatePrinterStatus: Update printer status: request: %s' % (request), file=sys.stderr)
            return 'OK'
        queue = data['queue']
        id = data['id']
        enabled = data['enabled']
        print('FlaskServer.updatePrinterStatus[%s] enabled: %s' % (id, enabled), file=sys.stderr)
        for k in ['left', 'center', 'right']:
            self.printers[id][k] = False
        self.printers[id][queue] = enabled
        self.setPrinterResults()
        #print('FlaskServer.updatePrinterStatus: %s, queue: %s enabled: %s' % (id, queue, enabled), file=sys.stderr)
        return 'OK'

    def updateImpinjStatus(self):
        try:
            data = request.get_json()
        except NameError:
            print('FlaskSEver.updateImpinjStatus: Impinj clicked: no request', file=sys.stderr) 
            print('FlaskSEver.updateImpinjStatus: Update Impinj status: request: %s' % (request), file=sys.stderr)
            return 'OK'
        id = data['id']
        enabled = data['enabled']
        print('updateImpinjStatus[%s]: enabled: %s AAAAA' % (id, enabled), file=sys.stderr)
        for k, v in self.impinjs.items():
            self.impinjs[k]['enabled'] = False
        self.impinjs[id]['enabled'] = enabled
        self.setImpinjResults()
        print('FlaskServer.updateImpinjStatus[%s] enabled: %s' % (id, enabled), file=sys.stderr)
        print('FlaskServer.updateImpinjStatus[%s] %s' % (id, self.impinjs[id]), file=sys.stderr)
        if self.impinjTCPProxy:
            self.impinjTCPProxy.change(target=self.impinjs[id]['hostaddr'], )
        return 'OK'

    def __init__(self, impinjTCPProxy=None, **kwargs):
        self.impinjTCPProxy = impinjTCPProxy
        self.semaphore = Semaphore()
        self.app1 = Flask(__name__)
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
        self.printerHeader = ['Name', 'Address', 'Status', 'Media', 'UpTime', 'Left', 'Center', 'Right', 'Last Seen',]
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
            print('FlaskServer.setImpinjResults[%d:%s]: info %s ' % (i, impinj, info), file=sys.stderr)
            hostname = info.get('hostname', None)
            hostaddr = info.get('hostaddr', None)
            macaddr = info.get('MACAddress', None)
            serialnumber = info.get('SerialNumber', None)
            address = f"<a href='http://{hostaddr}'>{hostaddr}</a>" if hostaddr else 'n/a'
            tooltip0 = f"{info.get('Model','')} {info.get('sysdescr','')}"

            seenElapsed = time.time() - info.get('lastSeen', 0)
            if seenElapsed > 10:
                print('FlaskServer.setImpinjResults[%d:%s]: seenElapsed: %s' % (i, impinj, seenElapsed), file=sys.stderr)
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

        #print('FlaskServer.setImpinjResults: results: %s' % self.impinjResults, file=sys.stderr)

    # called by the main thread to update
    def impinjUpdate(self, impinjInfo=None):
        # update the impinjs dictionary
        print('FlaskServer.impinjUpdate: impinjInfo: %s' % impinjInfo, file=sys.stderr)
        with self.semaphore:
            for i, (impinj, info) in enumerate(impinjInfo.items()):
                if impinj not in self.impinjs:
                    self.impinjs[impinj] = {}
                    if len(self.impinjs) == 1:
                        self.impinjs[impinj] = {'enabled': True, }
                        self.impinjTCPProxy.change(target=info.get('hostaddr', None), )
                        print('FlaskServer.update[%d:%s]: impinj %s EMPTY' % (i, impinj, self.impinjs[impinj]), file=sys.stderr)
                self.impinjs[impinj]['lastSeen'] = time.time()
                if info:
                    for j, (k, v) in enumerate(info.items()):
                        #print('FlaskServer.update[%d:%d:%s]: k: %s, v: %s' % (i, j, impinj, k, v), file=sys.stderr)
                        self.impinjs[impinj][k] = v
                        #print('FlaskServer.update[%d:%d:%s]: impinj %s' % (i, j, impinj, self.impinjs[impinj]), )
        
        #print('FlaskServer.impinjUpdate: impinjs: %s' % self.impinjs, file=sys.stderr)
        self.setImpinjResults()

    def setPrinterResults(self):
        self.printerResults = []
        self.lastPrintersUpdate = time.time()
        for i, (printer, info) in enumerate(self.printers.items()):
            #print('FlaskServer.setPrinterResults[%d:%s]: info %s' % (i, printer, info), file=sys.stderr)
            hostaddr = info.get('hostaddr', None)
            hostname = info.get('hostname', None)
            macaddr = info.get('MACAddress', None)
            serialnumber = info.get('SerialNumber', None)
            address = f"<a href='http://{hostaddr}'>{hostaddr}</a>" if hostaddr else 'n/a'
            tooltip0 = f"{info.get('Model','')} {info.get('sysdescr','')}"
            seenElapsed = time.time() - info.get('lastSeen', 0)
            if seenElapsed > 10:
                print('FlaskServer.setPrinterResults[%d:%s]: seenElapsed: %s' % (i, printer, seenElapsed), file=sys.stderr)
            self.printerResults.append({
                'id': printer,
                'name': hostname, 
                'address': info.get('hostaddr',''),
                'tooltip0': tooltip0,
                'status': info.get('Status',''),
                'media': info.get('Media',''),
                'left': info.get('left', False),
                'center': info.get('center', False),
                'right': info.get('right', False),
                'SysUpTime': self.sysUpTime(info.get('SysUpTime', 0)),
                'lastSeen': datetime.datetime.utcfromtimestamp(seenElapsed).strftime('%H:%M:%S') if seenElapsed > 10 else '< 10s',
                }
            )
        #print('FlaskServer.printerUpdate: results: %s' % self.printerResults, file=sys.stderr)

    def printerUpdate(self, printerInfo=None):
        #print('FlaskServer.update: vvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvvv', file=sys.stderr)
        #print('FlaskServer.update: printerInfo: %s' % printerInfo, file=sys.stderr)
        with self.semaphore:
            for i, (printer, info) in enumerate(printerInfo.items()):
                macaddr = info.get('MACAddress', None)
                serialnumber = info.get('SerialNumber', None)
                if printer not in self.printers:
                    self.printers[printer] = {'left': False, 'center': True, 'right': False, }
                    #print('FlaskServer.update[%d:%s]: printer %s EMPTY' % (i, printer, self.printers[printer]), file=sys.stderr)
                self.printers[printer]['lastSeen'] = time.time()
                if info:
                    for j, (k, v) in enumerate(info.items()):
                        self.printers[printer][k] = v
        #print('FlaskServer.update: --------------------------------------------', file=sys.stderr)
        #print('FlaskServer.update: printers: %s' % self.printers, file=sys.stderr)
        #for i, (k, v) in enumerate(self.printers.items()):
        #    print('FlaskServer.update[%d]: printer %s: %s' % (i, k, v), file=sys.stderr)
        #print('FlaskServer.update: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^', file=sys.stderr)
        #for i, (k, v) in enumerate(self.printers.items()):
        #    print('FlaskServer.update[%d:%s] %s' % (i, k, v), file=sys.stderr)

        self.setPrinterResults()

    def run(self):
        print('run: Starting server', file=sys.stderr)
        self.server.serve_forever()
        print('run: server started', file=sys.stderr)

    def shutdown(self):
        print('Stopping server', file=sys.stderr)
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
        print('SIGINT received %s' % (signal,), file=sys.stderr)
        sigintEvent.set()
        changeEvent.set()

    signal.signal(signal.SIGINT, lambda signal, frame: sigintHandler(signal, frame))

    server = FlaskServer()
    server.start()

    while changeEvent.wait():
        changeEvent.clear()
        if sigintEvent.is_set():
            stopEvent.set()
            print('Shutting down server', file=sys.stderr)
            server.shutdown()
            print('Server shutdown', file=sys.stderr)
            break

if __name__ == '__main__':

    main()

