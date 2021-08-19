#!/usr/bin/env python3
# vim: expandtab shiftwidth=4 tabstop=4
#
# RaceDB QLLabels Python Script
#
# Usage
# In the RaceDB System Info Edit screen:
#
#   Cmd used to print Bib Tag (parameter is PDF file)
#
#       [  /home/RaceDB/scripts/QLLABELS.py $1 ]
# 
# This script will convert the PDF file to Brother Raster file(s) and 
# send the Raster file(s) to a Brother QL style label printer or to 
# the qlmuxd printer spooler.
#
# N.b. the file name is provided as a parameters, the PDF data is also
# provided on stdin.
# 
# Sending the files directly to the printers on port 9100 works, but 
# only when # there is only a single person using RaceDB. Multiple prints 
# to a QL printer will result in over lapping labels.
#
# The qlmuxd program manages pools of QL printers and will spool
# the data allowing multiple people to print to them, with support
# for different printers for the different antennas and fall-over
# support if (when) the printers are not available (typically when
# they run out of labels. The qlmuxd program takes the same raster
# file data that would be sent to the printers on port 9100, but
# uses ports 910N to allow us to specify which pool of printers
# to use.
#
# This script will get labels printed (either directly or via qlmuxd) 
# far faster than CUPS using the standard Brother QL support files.
#
# This script will:
#
#   1. Convert $1 to $1-$PAGENO.png for each page in the PDF file
#   2. Convert each page to $1-$PAGENO.rast
#   3. Equivalent of cat $1-*.rast | netcat $PRINTER_HOST $PRINTER_PORT
#
#
# The argument provided is the file name which contains information about what is to 
# be printed. E.g.:
#
#       230489203498023809_bib-356_port-8000_antenna-2_type-Frame.pdf
#
# "type" is one of Frame, Body, Shoulder or Emergency.
# "port" is the RaceDB server port.
# "antenna" is the antenna of the user.
#
# The combination of server port and antenna allows different printers to 
# be used for different registration stations. The server port refers to
# the TCP port that the server responds to, e.g. 8000 or 8001 etc.
#

import sys
import os
import socket
import subprocess
import jsoncfg
import json

import pdf2image
from pdf2image import convert_from_path
from pdf2image import convert_from_bytes

import sys
import datetime
getTimeNow = datetime.datetime.now

def usage(s):
    log('Usage: QLLABELS.py 130489203498023809_bib-719_port-8000_antenna-1_type-Frame.pdf')
    log('       %s' % (s))
    exit(1)

def log(s):
        print('%s %s' % (getTimeNow().strftime('%H:%M:%S'), s.rstrip()), file=sys.stderr)

# get the filename provided as the first arguement
#
try:
    fname = os.path.basename(sys.argv[1])
except:
    usage('No filename arguement')


print('fname: %s' % (fname))


# parse qlabels.cfg to get:
#
#   label sizes dictionary - map types to size, small or large
#   label pools dictionary - map port-antenna to pool for small and large to a pool name
#   label printers dictionary - hostname and port to use for a each pool
#
cfgs = ['/usr/local/etc/qllabels.cfg', 'qllabels.cfg']
config = None
for c in cfgs:
    try:
        config = jsoncfg.load_config(c)
        break
    except Exception as e:
        log('QLLABELS: error cannot open: %s %s' % (c, e))
        continue
if config is None:
    log('QLLABELS: error cannot open either: %s' % cfgs)
    exit(1)

# get the dictionaries
sizes = config.QLLABELS_Sizes()
pools = config.QLLABELS_Pools()
printers = config.QLLABELS_Printers()

#print('sizes: %s' % (sizes))
#print('printers: %s' % (printers))
#print('pools: %s' % (pools))

# Split file name apart to get information about the label.
#   bib, port, antenna and type parameters
# e.g:
#   230489203498023809_bib-719_port-8000_antenna-0_type-Frame.pdf
#
# Numeric fields are converted to numbers to allow comparisons like params['antenna'] == 1

#{ print('p: %s' % ('%s-none' %p)) for p in os.path.splitext(fname)[0].split('_')[:]  }
#{ print('k: %s v: %s' % (k, v)) for k, v in (p.split('-') for p in os.path.splitext(fname)[0].split('_')[:])  }

# N.B. we have seen the random number as prefix and suffix, this allows us to ignore it at either end
params = { k:(int(v) if v.isdigit() else v) for k, v in (('%s-none' % p).split('-')[:2] for p in os.path.splitext(fname)[0].split('_')[:] ) }

print('params: %s' % (params))

try:
    size = sizes[params['type']]
except:
    usage('Do not understand type-%s' % (params['type']))
#print('size: %s' % (size))

poolMatch = "%s-%d" % (params['port'], params['antenna'])
try:
    pool = pools[poolMatch]
except:
    usage('Do not understand %s' % (poolMatch))
#print('pool: %s' % (pool))

try:
    printerName = pool[size]
except:
    usage('Do not understand printerName %s' % (printerName))
#print('printerName: %s' % (printerName))

try:
    printer = printers[printerName]
except:
    usage('Cannot find printerName %s' % (printerName))
#print('printer: %s' % (printer))

try:
    hostname = printer['hostname']
    port = printer['port']
    model = printer['model']
    labelsize = printer['labelsize']
except:
    usage('Cannot find one of hostname, port, model, labelsize: %s' % (printer))
    usage()

print('hostname: %s port: %d model: %s labelsize: %s' % (hostname, port, model, labelsize))


# convert PDF to PNG images using pdf2image (poppler), data from stdin,
# then save each image separately as a png.
#
#images = convert_from_path('/dev/stdin', size=(1109, 696), dpi=280, grayscale=True)
bytes = sys.stdin.read()
images = convert_from_bytes(bytes, size=(1109, 696), dpi=280, grayscale=True)

last = 0
for index, image in enumerate(images):
    image.save(f'/tmp/{fname}-{index}.png')
    last = index

# convert PNG images to Brother Raster file, Note we use --no-cut for 0..N-1, 
# the last file will have a cut so that multiple labels will be kept together.
#
if last >= 1:
    for index in range(0, last):
        print('image: %d NO-CUT' % index)
        try:
            subprocess.check_call([
                'brother_ql_create', 
                '--rotate', '90', 
                '--model', model, 
                '--label-size', labelsize, 
                '--no-cut',
                f'/tmp/{fname}-{index}.png', 
                f'/tmp/{fname}-{index}.rast' ]) ;
        except Exception as e:
            log('brother_ql_create exception: %s' % (e))
            exit(1)

try:
    subprocess.check_call([
        'brother_ql_create', 
        '--rotate', '90', 
        '--model', model, 
        '--label-size', labelsize, 
        f'/tmp/{fname}-{last}.png', 
        f'/tmp/{fname}-{last}.rast' ]) ;
except Exception as e:
    log('brother_ql_create exception: %s' % (e))
    exit(1)



# Send *.rast to qlmuxd or direct to printer
#
s = socket.socket()
try:
    s.connect((hostname, port))
except Exception as e:
    print('s.connect(%s,%d) %s' % ( hostname, port, e))
    exit(1)

for index in range(0, last+1):
    with open(f'/tmp/{fname}-{index}.rast', "rb") as f:
        while True:
            bytes_read = f.read(4096)
            if not bytes_read:
                break
            s.sendall(bytes_read)
s.close()

# remove the intermediate files
#
#for index in range(0, last):
#    os.remove('/tmp/{fname}-{index}.png')
#    os.remove('/tmp/{fname}-{index}.rast')

