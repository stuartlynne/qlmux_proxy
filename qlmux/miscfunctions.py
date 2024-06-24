from yattag import Doc, indent
from .utils import log
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
                    doc.asis(self.text)
        return indent(doc.getvalue())   

class MiscFunctions(Script):
    _text = """
        var dropdownInUse = false;

        function isDropdownFocused() {
            return dropdownInUse;
        }

        document.addEventListener('focus', function(event) {
            console.log('focus: %s', event.target.tagName);
            if (event.target.tagName === 'SELECT') {
                dropdownInUse = true;
            }
        }, true);

        document.addEventListener('blur', function(event) {
            console.log('blur: %s', event.target.tagName);
            if (event.target.tagName === 'SELECT') {
                dropdownInUse = false;
            }
        }, true);

        document.addEventListener('change', function(event) {
            console.log('change: %s', event.target.tagName);
            if (event.target.tagName === 'SELECT') {
                dropdownInUse = false;
            }
        }, true);

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

        function setLastSeenCell(cell, lastSeen) {
            cell.textContent = lastSeen 
            if (lastSeen.includes('10s')) {
                cell.style.backgroundColor = '';
            } else {
                cell.style.backgroundColor = 'lightcoral';
            }
        }
        function addLastSeenCell(row, lastSeen) {
            var cell = row.insertCell();
            cell.textContent = lastSeen 
            if (lastSeen.includes('10s')) {
                cell.style.backgroundColor = '';
            } else {
                cell.style.backgroundColor = 'lightcoral';
            }
        }

        function addStatusCell(row, status) {
            var cell = row.insertCell();
            cell.textContent = status;
            switch(status) {
                case 'READY':
                    cell.style.backgroundColor = '';
                    break;
                case 'BUSY':
                    cell.style.backgroundColor = 'lightgreen';
                    break;
                default:
                    cell.style.backgroundColor = 'lightcoral';
                    break;
            }
            return cell;
        }

        function addMediaCell(row, status) {
            var cell = row.insertCell();
            cell.textContent = status === '' ? 'No Media' : status;
            cell.style.backgroundColor = status === '' ? 'lightcoral' : '';
            return cell;
        }

        function setTime(tableHeader, timeString) {
            // Check if the tableHeader has rows
            if (tableHeader.rows.length > 0) {
                // Get the first row
                var firstRow = tableHeader.rows[0];
                // Check if the first row has cells
                if (firstRow.cells.length > 0) {
                    // Get the last cell in the first row
                    var timeCell = firstRow.cells[firstRow.cells.length - 1];
                    // Update the text content of the last cell
                    timeCell.textContent = timeString;
                }
            }
        }

        function addRowsOnMessage(addRow, table, tableHeader, tableDescription, data) {
            console.log('addRowsOnMessage[%s] table', tableDescription);
            console.log('addRowsOnMessage[%s] replaceTable', data.replaceTable);
            // Replace table rows and build new table
            // Clear existing rows

            if (tableDescription !== 'QLmux Proxy') {
                if (isDropdownFocused()) {
                    console.log('addRowsOnMessage[%s]: dropdown focused, skipping update', tableDescription);
                    return
                }
            }
            
            if (data.replaceTable) {
                tableHeader.innerHTML = '';
                table.innerHTML = '';
            }
            replaceTable = tableHeader.innerHTML === '';

            if (replaceTable) {
                if (tableDescription == 'QLmux Proxy') {
                    var headerRow = tableHeader.insertRow();
                    var labelCell = headerRow.insertCell();
                    labelCell.colSpan = data.header.length - 1;
                    labelCell.textContent = tableDescription;
                    labelCell.addEventListener('click', function() {
                        if (tableDescription === 'Printers') {
                            printerTitleClicked(labelCell);
                        } else {
                            impinjTitleClicked(labelCell);
                        }
                    });

                    var timeCell = headerRow.insertCell();
                    timeCell.textContent = data.lastUpdate;
                    timeCell.addEventListener('click', function() {
                        if (tableDescription === 'Printers') {
                            printerTimeClicked(timeCell);
                        } else {
                            impinjTimeClicked(timeCell);
                        }
                    });
                }

                if (tableDescription !== 'QLmux Proxy') {
                    var headerRow = tableHeader.insertRow();
                    data.header.forEach(function (header) {
                        var cell = headerRow.insertCell();
                        cell.textContent = header;
                    });
                }
            } 
            else {
                if (tableDescription === 'QLmux Proxy') {
                    console.log('addRowsOnMessage: impinj lastUpdate: %s', data.lastUpdate);
                    setTime(tableHeader, data.lastUpdate);
                }
            }
            replaceTable = table.innerHTML === '';

            console.log('addRowsOnMessage: table.innerHTML: %s', table.innerHTML);
            console.log('addRowsOnMessage: replaceTable: %s', replaceTable);

            // iterate through data and update table values for
            // last seen, status, media, etc.
            // Add new rows with updated data
            if (tableDescription !== 'QLmux Proxy') {
                data.results.forEach(function (device) {
                    addRow(table, tableHeader, device, replaceTable); // XXX??
                });
            }

        }

        function addEventSource(url, addRow, addRowsOnMessage, table, tableHeader, event, tableDescription) {
            var eventSource = new EventSource(url);
            eventSource.onmessage = function (event) {
                var data = JSON.parse(event.data);
                console.log('addEventSource: %s', data);
                console.dir(data);
                addRowsOnMessage(addRow, table, tableHeader, tableDescription, data);
            }
            return eventSource;
        }

        function printerTitleClicked(cell) {
            sendPost(cell, '/printerTitleClicked', {});
        }

        function printerTimeClicked(cell) {
            sendPost(cell, '/printerTimeClicked', {});
        }

        function impinjTitleClicked(cell) {
            sendPost(cell, '/impinjTitleClicked', {});
        }

        function impinjTimeClicked(cell) {
            sendPost(cell, '/impinjTimeClicked', {});
        }

    """


