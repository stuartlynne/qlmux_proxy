# QLMux
## Copyright (c) 2018, stuart.lynne@gmail.com
## Sat Sep 01 18:31:24 PDT 2018 

*QLMux* is designed to support label printing to Brother QL printers that are set up in pools to allow for increased throughput 
and redundancy.

Printer pools are set up listing available printers, both a primary set and backup set, with an associated TCP port that will 
be used to accept label jobs:

> small1: 9001, (ql710w1, ql710w2), (ql710w3)
> small2: 9002, (ql710w3, ql710w2), (ql710w1)
> large1: 9003, (ql1060n1), (ql1060n2)
> large2: 9004, (ql1060n2), (ql1060n1)
> status: 9000

In the above there are two pools of small label printers that utilize three printers. One printer is shared to both pools, with the non-shared printers used as backups.  
  
There are two pools of large label printers, each with a single printer as primary and the other pools printer as backup.

Incoming jobs are accepted on the specified port and forwarded to port 9100 on one of the associated printers.

The incoming label print jobs are multiplexed across any working printers in the primary list. If non of the printers in the primary list are working the backup printer is used.

The binary data (typically under 100 kbytes) is kept in memory until it can be delivered. The intended
design is for about a half dozen printers with a load of about one label per second per printer maximum.

A status is kept for each printer so that fall over can be used to do the following:

  1. Level load across the printers
  2. Ensure that printers that are not available or not working are not used
  3. Minimize printing delays
  4. Ensure that all labels are printed, duplicates are allowed.

Depending on the printer status, when data has arrived and is in the DataQueue, QLMux will attempt
to deliver to the first available printer in the associated Pool. 

QLMux uses SNMP to check the current printer status for all specified printers. Printers that are
not in the ready state will not be used. Brother QL printers typically have four states:

  1. Ready - powered, turned on, 
  2. Cover Open - the printer is reporting that it's cover is open
  3. Not available 
    1. not powered, 
    2. not turned on, 
    3. not connected to the network.
  4. Error - the printer is reporting an error, typically one of
    1. Out of labels
    2. Labels are jammed
    3. Cut bar is jammed
    4. Wrong labels are loaded for the print job



A user friendly text showing any printers in error can be retrived from the specified status port. 

> [ ql710w1: Printer Cover Open, close cover ]
> [ ql1060n0: Not Available, check if powered off or not plugged in ]


This can be used in a script to return error information to a user.

> netcat 127.0.0.1 9001 < label.bin
> status = $(netcat 127.0.0.1 9000)




## Required packages

#### Linux packages
  - libpython-dev
  - libsnmp-dev

### Python packages
  - enum34
  - easysnmp
  

## Other Programs

  - qlprint (modified version for printing to stdout)
  - init.d script
  - libpng16.so.16:


