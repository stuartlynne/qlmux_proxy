
from enum import Enum
from .miscfunctions import Script
from .utils import log


class TableRowListener(Script):
    _addRow = None
    def __init__(self, tableName=None, scriptName=None, addRow=None, headers=None, src=None, text=None, tableDescription=None):
        super(TableRowListener, self).__init__(src=None, text=None, )
        log('TableRowListener: tableName: %s, scriptName: %s' %(tableName, scriptName), )
        self.tableName = tableName
        self.scriptName = scriptName
        self.tableDescription = tableDescription if tableDescription else 'Devices'
        self.text = f"""
            document.addEventListener('DOMContentLoaded', function () {{
                var table = document.getElementById('{self.tableName}').getElementsByTagName('tbody')[0];
                var tableHeader = document.getElementById('{self.tableName}').getElementsByTagName('thead')[0];
                console.log('TableRowListener: table: %s', table);
                console.dir(table);
                var eventSource = addEventSource('{self.scriptName}', {addRow}, {headers}, addRowsOnMessage, table, tableHeader, event,
                        '{self.tableDescription}');
            }});
            """
        if addRow:
            self.text += self._addRow

class TitleTableListener(TableRowListener):
    def __init__(self, tableName=None, scriptName=None, addRow=None, headers=None):
        self.header = f"""
            """
            
        self._addRow = f"""
            var TitleHeaders = ['Qlmux Proxy', ''];
            function titleAddRow(table, tableheader, device, replaceTable) {{
                console.log('titleAddRow: %s replaceTable: %s', device, replaceTable);
            }}

            """

        super(TitleTableListener, self).__init__(tableName=tableName, scriptName=scriptName, addRow=addRow, headers=headers, 
             tableDescription='QLmux Proxy')

class NetstatTableListener(TableRowListener):

    def __init__(self, tableName=None, scriptName=None, addRow=None, headers=None):
        self._addRow = f"""
            var NetstatHeaders = ['Ethernet', '(gw)', 'WiFi', '(gw)', 'WireGuard', '(gw)', 'Test 1', 'Test 2'];


            const netstatToolTips = {{
                'Ethernet': 'Current Ethernet connection status',
                'WiFi': 'Current WiFi connection status',
                'WireGuard': 'Current WireGuard connection status',
                'Well Known': 'Ability to ping well known addresses',
                }}

            function netstatAddDropdownCell(row, device) {{
                //var cell = row.insertCell();
                cell.appendChild(select);
                return cell;
            }}

            function setListenTip(cell, proxyAddress) {{
                var tooltip = ''
                tooltip = netstatToolTips[proxyAddress];
                if (cell.title !== tooltip) {{
                    cell.title = tooltip;
                    console.log('setListenTip: tooltip: %s', tooltip);
                }}
            }}

    function set_background_color(ping, dup) {{
        if (dup) {{
            return 'coral';
        }} else if (ping) {{
            return 'lightgreen';
        }} else {{
            return 'yellow'
        }}
    }}

    function netstatAddRow(table, tableheader, device, replaceTable) {{
        console.log('netstatAddRow: %s replaceTable: %s', device, replaceTable);
        console.dir(device);
        
        var row = document.getElementById(device.id);

        if (!row) {{
            console.log('netstatAddRow: ZZZZ');
            console.log('netstatAddRow: %s', device);
            console.dir(device);

            // Create empty arrays to store data for each interface
            //var interfaces = ['', '', '', ''];
            //var avgs = ['', '', '', ''];
            //var wellknown = [];
            //var wellavg = [];

            color1 = ['','', '','', '','', ];
            content1 = ['','', '','', '','', ];
            content2 = ['','', '','', '','', ];

            // Iterate through each network interface in the device data
            device.networkInfo.forEach(function(info) {{
                console.log('netstatAddRow: %s', info);
                console.dir(info);
                var ipaddr = info.ip;
                var gwaddr = info.gw;
                var ipAvg = info.ipAvg;
                var gwAvg = info.gwAvg;

                ipColor = set_background_color(info.ipPing, info.ipDup);
                gwColor = set_background_color(info.gwPing, info.gwDup);
                console.log('netstatAddRow: %s addr: %s dup: %s ping: %s %s', info.interface, ipaddr, info.ipDup, info.ipPing, ipColor );
                console.log('netstatAddRow: %s addr: %s dup: %s ping: %s %s', info.interface, gwaddr, info.gwipDup, info.gwipPing, gwColor );
                if (info.interface.startsWith('en')) {{
                    content1[0] = ipaddr;
                    content1[1] = gwaddr;
                    content2[0] = ipAvg;
                    content2[1] = gwAvg;
                    color1[0] = ipColor;
                    color1[1] = gwColor;
                }} else if (info.interface.startsWith('wl')) {{
                    content1[2] = ipaddr;
                    content1[3] = gwaddr;
                    content2[2] = ipAvg;
                    content2[3] = gwAvg;
                    color1[2] = ipColor;
                    color1[3] = gwColor;
                }} else if (info.interface.startsWith('wg')) {{
                    content1[4] = ipaddr;
                    content1[5] = gwaddr;
                    content2[4] = ipAvg;
                    content2[5] = gwAvg;
                    color1[4] = ipColor;
                    color1[5] = gwColor;
                }} else if (info.interface === 'well known') {{
                    content1.push(ipaddr);
                    content2.push(ipAvg);
                    color1.push(set_background_color(info.ipPing, info.ipDup));
                }}

            }});

            // Insert the first row for IP and Gateway addresses
            var row1 = table.insertRow();
            row1.id = device.id;
            for (var i = 0; i < content1.length; i++) {{
                row1.insertCell();
                var cell = row1.cells[i];
                cell.style.backgroundColor = color1[i];
                cell.textContent = content1[i];
            }}

            // Insert the second row for average ping times
            var row2 = table.insertRow();
            row2.id = device.id;
            for (var i = 0; i < content2.length; i++) {{
                var rounded = Math.round(content2[i]);
                if (rounded != 0) {{
                    row2.insertCell().textContent = rounded + ' ms';
                }}
                else {{
                    row2.insertCell().textContent = '';
                }}
                //var cell = row2.cells[i];
                //cell.style.backgroundColor = color1[i];
                //cell.textContent = content2[i];
            }}
        }}

    }}






        """
        super(NetstatTableListener, self).__init__(tableName=tableName, scriptName=scriptName, addRow=addRow, 
                           headers=headers, tableDescription='Network Status')



class ImpinjsTableListener(TableRowListener):

    def __init__(self, tableName=None, scriptName=None, addRow=None, headers=None):
        self._addRow = f"""
            var ImpinjHeaders = ['RFID Reader', 'Address', 'Client', 'Stats', 'Last Seen / UpTime', 'RFID Proxy', 'Select' ];
            const ImpinjHeader = {{
                NAME: 0,
                ADDRESS: 1,
                CLIENT: 2,
                STATS: 3,
                LASTSEENUPTIME: 4,
                PROXYPORT: 5,
                SELECT: 6
                }}

            const impinjToolTips = {{
                '127.0.0.1': 'RaceDB RFID_READER_HOST=127.0.0.1',
                '127.0.0.2': 'RaceDB RFID_READER_HOST=127.0.0.2',
                '127.0.0.3': 'RaceDB RFID_READER_HOST=127.0.0.3',
                'Disabled': 'Disabled',
                }}

            function impinjAddDropdownCell(row, device) {{
                //var cell = row.insertCell();
                var cell = row.cells[ImpinjHeader.SELECT];
                var select = document.createElement('select');
                var options = ['127.0.0.1', '127.0.0.2', '127.0.0.3', 'Disabled', ];
                console.log('impinjAddDropdownCell: options: %s queue: %s', options, device.queue);

                options.forEach(function (option) {{
                    var opt = document.createElement('option');
                    opt.value = option;
                    opt.text = option;
                    if (option === device.proxyAddress) {{
                        opt.selected = true;
                    }}
                    select.appendChild(opt);
                }});
                cell.appendChild(select);
                select.addEventListener('change', function () {{
                    console.log('impinjAddDropdownCell: id: %s select: %s', device.id, select.value);
                    sendPost(cell, '/updateImpinjStatus', {{ id: device.id, proxyAddress: select.value, }});
                    //sendPost(enabledCell, '/updateImpinjStatus', {{ id: device.id, enabled: !device.enabled }});
                }});
                return cell;
            }}

            function setListenTip(cell, proxyAddress) {{
                var tooltip = ''
                tooltip = impinjToolTips[proxyAddress];
                if (cell.title !== tooltip) {{
                    cell.title = tooltip;
                    console.log('setListenTip: tooltip: %s', tooltip);
                }}
            }}

            // Function to add device data to the table
            function impinjAddRow(table, tableheader, device, replaceTable) {{
                console.log('impinjAddRow: %s replaceTable: %s', device, replaceTable);
                console.dir(device);
                row = document.getElementById(device.id);

                var row = document.getElementById(device.id);
                if (!row) {{
                    console.log('impinjAddRow: ZZZZ')
                    var row = table.insertRow();
                    row.id = device.id;

                    for (var i = 0; i < Object.keys(ImpinjHeader).length; i++) {{ row.insertCell(); }}


                    dropdown = impinjAddDropdownCell(row, device);
                    dropdown.title = "Select Target address for device, as seen in the RaceDB Container" +
                        "\\n127.0.0.1+N - requires rfidproxy.py in the RaceDB container" +
                        "\\nEach RFID reader must have a unique target address";

                    //setLastSeenCell(row.cells[ImpinjHeader.LASTSEEN], device.lastSeen);

                    row.cells[ImpinjHeader.NAME].title = device.tooltip0;
                    row.cells[ImpinjHeader.ADDRESS].title = 'Click to open device Web Adminstration Page';
                    row.cells[ImpinjHeader.CLIENT].title = 'IP Address of the client connecting to the RFID Reader';
                    row.cells[ImpinjHeader.STATS].title = 'TCP transfers to/from the RFID Reader';

                    row.addEventListener('click', function () {{
                        var impinjName = device.id;
                        sendPost(row, '/impinjClicked', {{ 'impinj_name': impinjName }});
                    }});

                }}

                //row.cells[ImpinjHeader.UPTIME].textContent = device.SysUpTime;
                //row.cells[ImpinjHeader.LASTSEEN].textContent = device.lastSeen;
                row.cells[ImpinjHeader.LASTSEENUPTIME].textContent = device.lastSeenUpTime;
                row.cells[ImpinjHeader.STATS].textContent = device.stats;

                var cell = row.cells[ImpinjHeader.PROXYPORT];
                if (cell.textContent !== device.proxyAddress) {{
                    cell.textContent = device.proxyAddress;
                    cell.style.backgroundColor = device.proxyAddress === 'Disabled' ? '' : 'lightgreen';
                    setListenTip(cell, device.proxyAddress);
                    console.log('impinjAddRow: listen tooltip: %s', row.cells[ImpinjHeader.PROXYPORT].title);
                }}

                if (
                    device.name === null || device.connectedChanged || 
                    row.cells[ImpinjHeader.NAME].textContent !== device.name ||
                    row.cells[ImpinjHeader.ADDRESS].textContent !== device.address ||
                    row.cells[ImpinjHeader.CLIENT].textContent !== device.clientAddress 
                    ) 
                {{
                    console.log('impinjAddRow: set name: %s client: %s connected: %s', 
                            device.name, device.client, device.connected);

                    // set textContent
                    row.cells[ImpinjHeader.NAME].textContent = device.name;
                    row.cells[ImpinjHeader.CLIENT].textContent = device.clientAddress;

                    // setup address link
                    var addressLink = document.createElement('a');
                    addressLink.href = 'http://' + device.address;
                    addressLink.textContent = device.address;
                    addressLink.target = '_blank';

                    // remove existing link and append new link
                    var addressCell = row.cells[ImpinjHeader.ADDRESS];
                    if (addressCell.firstChild && addressCell.firstChild.tagName === 'A') {{
                        addressCell.removeChild(addressCell.firstChild);
                    }}
                    addressCell.appendChild(addressLink);

                    // set background color based on connected status
                    var backgroundColor = device.connected ? 'lightgreen' : '';
                    row.cells[ImpinjHeader.CLIENT].style.backgroundColor = backgroundColor;
                    addressCell.style.backgroundColor = backgroundColor;

                    console.log('impinjAddRow: set address: %s', device.address);
                }}

                setLastSeenCell(row.cells[ImpinjHeader.LASTSEENUPTIME], device.lastSeenUpTime);
            }}
        """
        super(ImpinjsTableListener, self).__init__(tableName=tableName, scriptName=scriptName, addRow=addRow, headers=headers, tableDescription='RFID Readers')


class PrintersTableListener(TableRowListener):

    def __init__(self, tableName=None, scriptName=None, addRow=None, headers=None):
        self._addRow = f"""
            var PrinterHeaders = ['Printer', 'Address', 'Status', 'Media', 'Stats', 'Last Seen / UpTime', 'Queue', 'Select'];
            const PrinterHeader = {{
                NAME: 0,
                ADDRESS: 1,
                STATUS: 2,
                MEDIA: 3,
                STATS: 4,
                LASTSEENUPTIME: 5,
                QUEUE: 6,
                SELECT: 7
            }};
            function printersAddDropdownCell(row, device) {{
                var cell = row.cells[PrinterHeader.SELECT];
                var select = document.createElement('select');
                var options = ['Left', 'Center', 'Right', 'Disabled'];

                options.forEach(function (option) {{
                    var opt = document.createElement('option');
                    console.log('printersAddDropdownCell: option: %s queue: %s', option, device.queue);
                    opt.value = option;
                    opt.text = option;
                    if (option.toLowerCase() === device.queue.toLowerCase()) {{
                        console.log('printersAddDropdownCell: option: %s queue: %s SELECTED', option, device.queue);
                        opt.selected = true;
                    }}
                    select.appendChild(opt);
                }});
                cell.appendChild(select);
                select.addEventListener('change', function () {{
                    console.log('printersAddDropdownCell: id: %s select: %s', device.id, select.value);
                    sendPost(cell, '/updatePrinterQueue', {{ id: device.id, queue: select.value }});
                    //sendPost(leftCell, '/updatePrinterStatus', {{ id: device.id, queue: select.value, enabled: !device.left }});
                }});
                return cell;
            }}

            function setQueue(cell, queue) {{
                cell.textContent = queue;
                cell.style.backgroundColor = queue === 'Disabled' ? '': 'lightgreen';
           }}

            // Function to add device data to the table
            function printerAddRow(table, tableheader, device, replaceTable) {{
                console.log('printerAddRow: %s replaceTable: %s', device.queue, replaceTable);
                console.dir(device);
                row = document.getElementById(device.id);
                if (!row) {{
                    console.log('printerAddRow: %s replaceTable: %s', device, replaceTable);
                    var row = table.insertRow();
                    row.id = device.id;
                    for (var i = 0; i < Object.keys(PrinterHeader).length; i++) {{ row.insertCell(); }}
                    // column 5 - select
                    dropdown = printersAddDropdownCell(row, device);
                    dropdown.title = 'Select Queue for Printer';

                }}
                if (row.cells[PrinterHeader.QUEUE].textContent !== device.queue) {{ 
                    setQueue(row.cells[PrinterHeader.QUEUE], device.queue);
                }}   

                // column 0 - name
                if (row.cells[PrinterHeader.NAME].textContent !== device.name) {{
                    row.cells[PrinterHeader.NAME].textContent = device.name;
                    row.cells[PrinterHeader.NAME].title = device.tooltip0;
                    row.cells[PrinterHeader.ADDRESS].title = 'Click to open device Web Adminstration Page';
                    var addressCell = row.cells[PrinterHeader.ADDRESS];
                    var addressLink = document.createElement('a');
                    addressLink.href = 'http://' + device.address;
                    addressLink.textContent = device.address;
                    addressLink.target = '_blank';
                    addressCell.appendChild(addressLink);
                }}
                if (row.cells[PrinterHeader.STATUS].textContent !== device.status) {{
                    row.cells[PrinterHeader.STATUS].textContent = device.status;
                    switch (device.status) {{
                    case 'READY': color = ''; break;
                    case 'BUSY': color = 'lightcoral'; break;
                    default: color = 'lightcoral'; break;
                    }}
                    row.cells[PrinterHeader.STATUS].style.backgroundColor = color
                }}

                if (row.cells[PrinterHeader.MEDIA].textContent !== device.media) {{
                    row.cells[PrinterHeader.MEDIA].textContent = device.media;
                    row.cells[PrinterHeader.MEDIA].style.backgroundColor = device.media === '' ? 'lightcoral' : '';
                }}

                //row.cells[PrinterHeader.UPTIME].textContent = device.SysUpTime;
                //row.cells[PrinterHeader.LASTSEEN].textContent = device.lastSeen;
                row.cells[PrinterHeader.LASTSEENUPTIME].textContent = device.lastSeen;

                if (row.cells[PrinterHeader.STATS].textContent !== device.stats) {{
                    row.cells[PrinterHeader.STATS].textContent = device.stats;
                }}

                setLastSeenCell(row.cells[PrinterHeader.LASTSEENUPTIME], device.lastSeenUpTime);

                //row.addEventListener('click', function () {{
                //    var printerName = device.id;
                //    sendPost(row, '/printerClicked', {{ 'printer_name': printerName }});
                //}});
            }}
        """

        super(PrintersTableListener, self).__init__(tableName=tableName, scriptName=scriptName, addRow=addRow, headers=headers, tableDescription='Printers')


