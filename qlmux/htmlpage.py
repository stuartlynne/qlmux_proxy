
import sys
from time import sleep, time
import traceback
from yattag import Doc, indent


class HtmlPage:
    def __init__(self, title, apis=None, scripts=None, head=None, elements=None, testpage=None):
        self.title = title
        self.head = head
        self.elements = elements if elements else []
        self.apis = apis if apis else []
        self.scripts = scripts if scripts else []
        self.testpage = testpage

    def __str__(self):
        doc, tag, text = Doc().tagtext()
        doc.asis('<!DOCTYPE html>')
        with tag('html', lang='en'):
            with tag('head'):
                with tag('meta', charset='UTF-8'): pass
                with tag('meta', name='viewport', content='width=device-width, initial-scale=1.0'): pass
                with tag('title'): text(self.title)
                for api in self.apis:
                    doc.asis(str(api))
                #with tag('link', href = "https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css", rel="stylesheet",): pass
                #with tag('script', src="https://code.jquery.com/jquery-3.5.1.min.js"): pass
                #with tag('style', type='text/css'):
                #    text('thead { font-weight: bold; color: white; background-color: #007bff; }')

            with tag('body'):
                with tag('div', klass="container mt-5"):
                    for element in self.elements:
                        doc.asis(str(element))
                doc.asis('<!-- Scripts -->')
                for script in self.scripts:
                    doc.asis(str(script))
                doc.asis('<!-- Test Page -->')
                if self.testpage:
                    doc.asis(self.testpage)
        return indent(doc.getvalue())

class Table:
    def __init__(self, name, id=None, columns=None, rows=None):
        self.name = name
        self.id = id
        self.columns = columns
        self.rows = rows

    def __str__(self):
        doc, tag, text = Doc().tagtext()
        with tag('table', id=self.id, klass='table table-striped table-bordered table-hover'):
            with tag('thead', id=f"{self.id}-header",): 
                doc.asis('<!-- Table header will be dynamically added here -->')
            with tag('tbody', id=f"{self.id}-body",): 
                doc.asis('<!-- Table body will be dynamically added here -->')
            #with tag('tr'):
            #    for column in self.columns:
            #        with tag('th'):
            #            text(column)
            #for row in self.rows:
            #    with tag('tr'):
            #        for cell in row:
            #            with tag('td'):
            #                text(cell)
        return indent(doc.getvalue())


class Link:
    def __init__(self, href='', text=''):
        self.href = href
        self.text = text

    def __str__(self):
        doc, tag, text = Doc().tagtext()
        with tag('link', href=self.href, rel='stylesheet'):
            text(self.text)
        return indent(doc.getvalue())

class Style:
    def __init__(self, type='text/css', text=''):
        self.type = type
        self.text = text

    def __str__(self):
        doc, tag, text = Doc().tagtext()
        with tag('style', type=self.type):
            text(self.text)
        return indent(doc.getvalue())

class Script:
    _src = None
    _text = None
    def __init__(self, src=None, text=None):
        self.src = self._src if src is None else src 
        self.text = self._text if text is None else text

    def __str__(self):
        doc, tag, text = Doc().tagtext()
        if self.src:
            with tag('src', src=self.src):
                pass
        else:
            with tag('script', ):
                if self.text:
                    text(self.text)
        return indent(doc.getvalue())   

class MiscFunctions(Script):
    _text = """
            // Send HTTP request to update server with new status
            function sendPost(cell, url, data) {
                console.log('sendPost: %s', url);
                console.dir(data);
                cell.style.backgroundColor = 'lightblue';
                var xhr = new XMLHttpRequest();
                xhr.open('POST', url, true);
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.send(JSON.stringify(data));
                setTimeout(function () { cell.style.backgroundColor = ''; }, 4000);
            }

            function addCell(row, text) {
                var cell = row.insertCell();
                cell.textContent = text;
            }
            // Set enabled/disabled status for cell, and color background
            function setEnabled(cell, enabled) {
                cell.textContent = enabled ? 'Enabled' : 'Disabled';
                cell.style.backgroundColor = enabled ? 'lightgreen' : '';
            }
            function addEnabledCell(row, enabled) {
                var cell = row.insertCell();
                setEnabled(cell, enabled);
                return cell;
            }
            function addLastSeenCell(row, lastSeen) {
                var cell = row.insertCell();
                cell.textContent = lastSeen 
                if (lastSeen.includes('10s')) {
                    cell.style.backgroundColor = '';
                    //console.log('addLastSeenCell: %s DEFAULT', lastSeen);
                }
                else {
                    cell.style.backgroundColor = 'lightcoral';
                    //console.log('addLastSeenCell: %s CORAL', lastSeen);
                }
            }
            function addStatusCell(row, status) {
                var cell = row.insertCell();
                cell.textContent = status;
                switch(status) {
                case 'READY':
                    cell.style.backgroundColor = '';
                    break
                case 'BUSY':
                    cell.style.backgroundColor = 'lightgreen';
                    break
                default:
                    cell.style.backgroundColor = 'lightcoral';
                    break
                }
                return cell;
            }
            function addMediaCell(row, status) {
                var cell = row.insertCell();
                cell.textContent = status === '' ? 'No Media' : status;
                cell.style.backgroundColor = status === '' ? 'lightcoral' : '';
                return cell;
            }
            function addRowsOnMessage(addRow, table, tableHeader, tableDescription, data) {
                // Clear existing rows
                table.innerHTML = '';
                tableHeader.innerHTML = '';
                // Add new rows with updated data
                data.results.forEach(function (device) {
                    //console.log('onmessage: device %s', device);
                    addRow(table, tableHeader, device);
                });
                var headerRow = tableHeader.insertRow();
                var labelCell = headerRow.insertCell();
                console.dir(data.header);
                labelCell.colSpan = data.header.length -1;
                //console.log('onmessage: colSpan: %s', labelCell.colSpan);
                //labelCell.textContent = 'Devices';
                labelCell.textContent = tableDescription;
                headerRow.insertCell().textContent = data.lastUpdate;
                var headerRow = tableHeader.insertRow();
                data.header.forEach(function (header) {
                    var cell = headerRow.insertCell();
                    cell.textContent = header;
                });
            }
            function addEventSource(url, addRow, addRowsOnMessage, table, tableHeader, event, tableDescription){
                var eventSource = new EventSource(url);
                eventSource.onmessage = function (event) {
                    // Parse JSON data from the event
                    var data = JSON.parse(event.data);
                    addRowsOnMessage(addRow, table, tableHeader, tableDescription, data);
                    }
                return eventSource;
            }
        """

#class EventListener(Script):

class TableRowListener(Script):
    _addRow = ''
    def __init__(self, tableName=None, scriptName=None, addRow=None, src=None, text=None, tableDescription=None):
        super(TableRowListener, self).__init__(src=None, text=None, )
        print('TableRowListener: tableName: %s, scriptName: %s' %(tableName, scriptName), file=sys.stderr)
        self.tableName = tableName
        self.scriptName = scriptName
        self.tableDescription = tableDescription if tableDescription else 'Devices'
        self.text = f"""
            document.addEventListener('DOMContentLoaded', function () {{
                var table = document.getElementById('{self.tableName}').getElementsByTagName('tbody')[0];
                var tableHeader = document.getElementById('{self.tableName}').getElementsByTagName('thead')[0];
                var eventSource = addEventSource('{self.scriptName}', {addRow}, addRowsOnMessage, table, tableHeader, event,
                '{self.tableDescription}');
            }});
            {self._addRow}
            """
        print('TableRowListener: %s' %(self.text), file=sys.stderr)

class PrintersTableListener(TableRowListener):
    _addRow = """
                // Function to add device data to the table
                function printerAddRow(table, tableheader, device) {
                    console.log('printerAddRow: %s', device);
                    //console.dir(device);
                    //console.log('printerAddRow: name: %s, status: %s, media: %s enabled: %s', device.name, device.status, device.media, device.enabled);
                    var row = table.insertRow();

                    addCell(row, device.name);
                    var addressCell = row.insertCell();
                    var addressLink = document.createElement('a');
                    addressLink.href = 'http://' + device.address;
                    addressLink.textContent = device.address;
                    addressLink.target = '_blank';
                    addressCell.appendChild(addressLink);

                    addStatusCell(row, device.status);
                    addMediaCell(row, device.media);
                    addCell(row, device.SysUpTime);

                    leftCell = addEnabledCell(row, device.left);
                    centerCell = addEnabledCell(row, device.center);
                    rightCell = addEnabledCell(row, device.right);

                    row.cells[0].title = device.tooltip0;
                    row.cells[1].title = 'Click to open device Web Adminstration Page';

                    addLastSeenCell(row, device.lastSeen);

                    // Add event listener to "Enabled" cell
                    leftCell.addEventListener('click', function () {
                        sendPost(leftCell, '/updatePrinterStatus', { id: device.id, queue: 'left', enabled: !device.left }); });
                    centerCell.addEventListener('click', function () {
                        sendPost(centerCell, '/updatePrinterStatus', { id: device.id, queue: 'center', enabled: !device.center }); });
                    rightCell.addEventListener('click', function () {
                        sendPost(rightCell, '/updatePrinterStatus', { id: device.id, queue: 'right', enabled: !device.right }); });

                    // Add event listener to row
                    row.addEventListener('click', function () {
                        var printerName = device.id;
                        sendPost(row, '/printerClicked', { 'printer_name': printerName });
                    });
                }

    """
    def __init__(self, tableName=None, scriptName=None, addRow=None,):
        super(PrintersTableListener, self).__init__(tableName=tableName, scriptName=scriptName, addRow=addRow, tableDescription='Printers' )
class ImpinjsTableListener(TableRowListener):
    _addRow = """
                // Function to add device data to the table
                function impinjAddRow(table, tableheader, device) {
                    console.log('impinjAddRow: %s', device);
                    //console.dir(device);
                    //console.log('impinjAddRow: name: %s, status: %s, media: %s enabled: %s', device.name, device.status, device.media, device.enabled);
                    var row = table.insertRow();

                    addCell(row, device.name);
                    var addressCell = row.insertCell();
                    var addressLink = document.createElement('a');
                    addressLink.href = 'http://' + device.address;
                    addressLink.textContent = device.address;
                    addressLink.target = '_blank';
                    addressCell.appendChild(addressLink);

                    addCell(row, device.status);
                    addCell(row, device.SysUpTime);
                    enabledCell = addEnabledCell(row, device.enabled);

                    addLastSeenCell(row, device.lastSeen);

                    row.cells[0].title = device.tooltip0;
                    row.cells[1].title = 'Click to open device Web Adminstration Page';

                    // Add event listener to "Enabled" cell
                    enabledCell.addEventListener('click', function () {
                        sendPost(enabledCell, '/updateImpinjStatus', { id: device.id, enabled: !device.enabled });
                    });

                    // Add event listener to row
                    row.addEventListener('click', function () {
                        // Send impinj name to server
                        var impinjName = device.id;
                        sendPost(row, '/impinjClicked', { 'impinj_name': impinjName });
                    });
                }
    """
    def __init__(self, tableName=None, scriptName=None, addRow=None,):
        super(ImpinjsTableListener, self).__init__(tableName=tableName, scriptName=scriptName, addRow=addRow, tableDescription='RFID Readers')

class TestPage:
        
    def __init__(self):
        pass

    def __str__(self):

        apis = [ 
            '<!-- Bootstrap CSS -->', Link('https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css', ''),
            '<!-- jQuery JS -->', Script("https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js", ''),
            '<!-- Bootstrap JS -->', Script('https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js'),
            '<!-- Styles -->', Style('text/css', 'thead { font-weight: bold; color: white; background-color: #007bff; }'),
        ]

        printers = Table('MyTable1', id='printers-table', columns=[], rows=[],)
        impinjs = Table('MyTable2', id='impinj-table', columns=[], rows=[],)

        misc = MiscFunctions()
        printerListener = PrintersTableListener(tableName='printers-table', scriptName='/printer_updates', addRow='printerAddRow')
        impinjListener = ImpinjsTableListener(tableName='impinj-table', scriptName='/impinj_updates', addRow='impinjAddRow')

        page = HtmlPage('Printers Status', apis=apis, elements=[printers, impinjs], scripts=[misc, printerListener, impinjListener, ], testpage=None)
        return str(page)
        #doc, tag, text = Doc().tagtext()
        #with tag('link', href=self.href, rel='stylesheet'):
        #    text(self.text)
        #return indent(doc.getvalue())




if __name__ == '__main__':

    printers = Table('MyTable1', id='printers-table', columns=[], rows=[],)
    impinjs = Table('MyTable2', id='impinj-table', columns=[], rows=[],)

    bootstrapCSS = Link('https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css', '')
    jqueryJS = Script("https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js", '')
    bootstrapJS = Script('https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js', '')
    misc = MiscFunctions()


    page = HtmlPage('xRaceDB Proxy', apis=[ 
        '<!-- jQuery JS -->',
        jqueryJS, 
        '<!-- Bootstrap CSS -->',
        bootstrapCSS,
        '<!-- Bootstrap JS -->',
        bootstrapJS, 
    ], scripts=[misc], elements=[printers, impinjs])

    print(page, file=sys.stderr)

