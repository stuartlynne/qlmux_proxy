# QLMux
## Copyright (c) 2018, stuart.lynne@gmail.com
## Sat Sep 01 18:31:24 PDT 2018 

*QLMux* is designed to support label printing to Brother QL printers that are set up in pools to allow for increased throughput 
and redundancy.

This was implemented to support label printing from RaceDB. 

QLMuxd loads a configuration file:

        1. ./qlmuxd.cfg
        2. /usr/local/etc/qlmuxd.cfg

The list of available printers with the associated printer model is specified in the configuration file.

        ql710w1, 'Brother QL-710W'
        ql710w2, 'Brother QL-710W'
        ql710w3, 'Brother QL-710W'
        ql1060n1, 'Brother QL-1060N'
        ql1060n2, 'Brother QL-1060N'

Printer pools are set up listing available printers, both a primary set and backup set, with an associated TCP port that will 
be used to accept label jobs: The expected media size is specified so that the SNMP monitoring can detect incorrectly installed
labels.

      small1: 9001, '62mm x 100mm', (ql710w1, ql710w2), (ql710w3)
      small2: 9002, '62mm x 100mm', (ql710w3, ql710w2), (ql710w1)
      large1: 9003, '102mm x 152mm', (ql1060n1), (ql1060n2)
      large2: 9004, '102mm x 152mm', (ql1060n2), (ql1060n1)
      status: 9000

In the above there are two pools of small label printers that utilize three printers. One printer is shared to both pools, with the non-shared printers used as backups. 

There are two pools of large label printers, each with a single printer as primary and the other pools printer as backup.

Incoming jobs are accepted on the specified port and forwarded to port 9100 on one of the associated printers.

The incoming label print jobs are multiplexed across any working printers in the primary list. 
If non of the printers in the primary list are working the backup printer is used. Backup printers
are only used when all primary printers are in an error mode.

The binary data (typically under 100 kbytes) is kept in memory until it can be delivered. The intended
design is for about a half dozen printers with a load of about one label per second per printer maximum.

A status is kept for each printer so that fall over can be used to do the following:

  1. Level load across the printers
  2. Ensure that printers that are not available or not working are not used
  3. Minimize printing delays
  4. Ensure that all labels are printed, duplicates are allowed.
  5. Ensure that the proper media is loaded for each printer.

Depending on the printer status, when data has arrived and is in the DataQueue, QLMux will attempt
to deliver to the first available printer in the associated Pool. 

QLMux uses SNMP to periodically check the current printer status for all specified printers. Printers that are
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

For each printer QLMux checks that the printer at the specified host address is the correct model.

For each pool QLMux checks that each member printer has the correct media loaded.

A user friendly text showing any printers in error can be retrived from the specified status port. 

     [ ql710w1: Printer Cover Open, close cover ]
     [ ql1060n0: Not Available, check if powered off or not plugged in ]


This can be used in a script to return error information to a user.

     netcat 127.0.0.1 9001 < label.bin
     status = $(netcat 127.0.0.1 9000)

There is also a qlstatus script to get the status data.


## Configuration

qlmuxd will look for a qlmuxd.cfg file in the current directory, and then in
/usr/local/etc/qlmuxd.cfg.

Sample.


        // QLMuxd configuration
        // This is for a five printer configuration.
        // There are four printer pools.
        //
        {

                // These are the pool listen ports
                //
                QLMux_Ports: [9001, 9002, 9003, 9004],

                // These are the printer destinations
                //
                QLMux_Printers: [
                     {name:"ql710w1",  model:"Brother QL-710W", port:9101},
                     {name:"ql710w2",  model:"Brother QL-710W", port:9102},
                     {name:"ql710w3",  model:"Brother QL-710W", port:9103},
                     {name:"ql1060n1", model:"Brother QL-1060N",port:9104},
                     {name:"ql1060n2", model:"Brother QL-1060N",port:9105},
                ],

                // These are the printer pools.
                // Pools map jobs directed at the listen port to the primary printers 
                // or if necessary the backup printers.
                QLMux_Pools: [
                    {name:"small1", listen:9001, media:"62mm x 100mm",  primaries:["ql710w1", "ql710w2"], backups:["ql710w3", ], },
                    {name:"small2", listen:9002, media:"62mm x 100mm",  primaries:["ql710w3", "ql710w2"], backups:["ql710w1", ], },
                    {name:"large1", listen:9003, media:"102mm x 152mm", primaries:["ql1060n1",         ], backups:["ql1060n2",], },
                    {name:"large2", listen:9004, media:"102mm x 152mm", primaries:["ql1060n2",         ], backups:["ql1060n1",], },
                ],

                // This is the status port
                //
                QLMux_StatusPorts: [
                    {name: "snmp", port: 9000 },
                ],
        }


## /etc/hosts
The simplest way to configure the QL Label printers is to assign static IP
addresses via /etc/hosts:

```
192.168.40.35   ql710w1
192.168.40.36   ql710w2
192.168.40.37   ql1060n1
192.168.40.38   ql710w3
192.168.40.39   ql1060n2
```

## Required packages

#### Linux packages
  - libpython-dev
  - libsnmp-dev

### Python packages
  - enum34
  - easysnmp
  - json-cfg  

## Other Programs

  - qlprint (modified version for printing to stdout)
  - brother_ql
  - init.d script
  - libpng16.so.16:


