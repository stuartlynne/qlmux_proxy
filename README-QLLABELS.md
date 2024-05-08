# QLLABELS.py
## Copyright (c) 2018-2024, stuart.lynne@gmail.com
## Thu May  2 05:01:13 PM PDT 2024

## Overview

This is a script that can be used from *RaceDB* to printer labels using the QLMux Proxy. It is a simple script that
converts the PDF file created by RaceDB to an image and then to the Brother Raster format, then
using the arguements passed to it, sends the label to the QLMux Proxy 
for printing on the correct size printer.

The conversion process keeps all data in memory (typically under 100 kbytes) and is very fast compared to
previous versions that used temporary files. 

The overall process uses the following steps:

1. Convert the PDF file to an image
'''
images = convert_from_bytes(sys.stdin.buffer.read(), size=imagesize[labelsize], dpi=280, grayscale=True)
'''

2. Convert the image to the Brother Raster format
'''
    qlr = BrotherQLRaster(model)
    instructions = convert(qlr, [image], **kwargs)
'''

3. Send the Brother Raster data to the QLMux Proxy via port 9100

The binary data (typically under 100 kbytes) is kept in memory until it can be delivered. The intended
design is for about a half dozen printers with a load of about one label per second per printer maximum
(that is the typical maximum print speed of the Brother Label Printers.)



## Installation 

There are two ways this can be used with RaceDB, both require a small script called lpr.

The lpr script can either call QLLABELS.py directly or it can use SSH to call QLLABELS.py in
the QLMux Proxy container.

### Directly
This involves adding the QLLABELS.py script to the RaceDB container. This is slightly
more complicated as there are multiple dependencies that need to be installed as well.

### SSH
This is simpler as the only dependency is the lpr script and the SSH client.
