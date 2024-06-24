
import sys
from time import sleep, time
import traceback
from yattag import Doc, indent
from .utils import log

from .miscfunctions import Script, MiscFunctions
from .tables import TableRowListener, TitleTableListener, ImpinjsTableListener, PrintersTableListener

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
                doc.asis('')
            with tag('tbody', id=f"{self.id}-body",): 
                doc.asis('')
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
            doc.asis(self.text)
        return indent(doc.getvalue())

class Style:
    def __init__(self, type='text/css', text=''):
        self.type = type
        self.text = text

    def __str__(self):
        doc, tag, text = Doc().tagtext()
        with tag('style', type=self.type):
            doc.asis(self.text)
        return indent(doc.getvalue())


#class EventListener(Script):

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

        title = Table('MyTable0', id='title-table', columns=[], rows=[],)
        printers = Table('MyTable1', id='printers-table', columns=[], rows=[],)
        impinjs = Table('MyTable2', id='impinj-table', columns=[], rows=[],)

        misc = MiscFunctions()
        titleListener = TitleTableListener(tableName='title-table', scriptName='/title_updates', addRow='titleAddRow')
        printerListener = PrintersTableListener(tableName='printers-table', scriptName='/printer_updates', addRow='printerAddRow')
        impinjListener = ImpinjsTableListener(tableName='impinj-table', scriptName='/impinj_updates', addRow='impinjAddRow')

        page = HtmlPage('Printers Status', apis=apis, elements=[title, printers, impinjs], scripts=[misc, titleListener, printerListener, impinjListener, ], testpage=None)
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

    log(page, )

