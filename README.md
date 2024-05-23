# QLMux Proxy
## Copyright (c) 2018-2024, stuart.lynne@gmail.com
## Thu May  2 05:01:13 PM PDT 2024

## Overview
This is the new version of *QLMuxd* that is designed to support label printing to 
Brother QL printers that are set up in pools to allow for increased throughput and redundancy
and act as a proxy for RaceDB to use a dynamically found RFID reader.

The new version uses SNMP broadcast discovery to find QL Label printers and Impinj RFID readers on the network and
automatically configure them for use if possible.

The goal is to:
- simplify the setup and use of the QL printers and RFID readers for events for RaceDB use.
- allow for easy swapping of printers and RFID readers without changing the RaceDB configuration.
- better diagnostics and control of the printers and RFID readers using a simple Web Status page.

## Installation as a Container

The QLMux Proxy is available as a Docker container. The container is based on the Alpine Linux distribution and is
very small. The container is available on Docker Hub as stuartlynne/qlmux_proxy.

Notes:
- the container must be run with the *--net=host* option to allow the container to find the printers and RFID readers on the network using *SNMP Broadcast Discovery*. 
- the qllabels program is in the container 
- an ssh server is running in the container to allow for external access to the qllabels program

Ports:
- 9101-9103 to allow for qllabels to push labels to the qlmux proxy.
- 9122 for access using ssh to run qllabels
- 9180 for the Web Status page

```
  sudo docker run \
          --detach \
          --name stuartlynne:qlmux_proxy/lastest \
          --net=host \
          --restart always \
          --env PYTHONUNBUFFERED=1 \  
          -v /etc/localtime:/etc/localtime:ro \
          -t qlmux_proxy
```

## QLMux
QLMux Proxy changes:

- no static configuration files
- use of SNMP Broadcast Discovery to find Brother label printers and Impinj RFID readers
- support for proxying traffic from to a found RFID router
- a web status page to monitor printer and RFID readers and effect some configuration for printer queues


*QLMux Proxy* was designed to support label printing to Brother QL printers that are set up in pools to allow for increased throughput 
and redundancy. The new version finds the printers dynamically using SNMP broadcast discovery. By default the printers are 
placed into a single pool, which is suitable for small events. For larger events, the printers can be placed into two different
pools to allow for increased throughput and redundancy using the builtin Web Status page.

*QLMux Proxy* also implements a transparent proxy for RaceDB to use a dynamically found RFID reader. This allows *RaceDB*
to use a single *IP address* and *port* to connect to the RFID reader. The *QLMux Proxy* will then forward the connection to the
correct RFID reader that is dynamically found. By default if only one RFID reader is found, it will be used. If more than one
RFD reader is found, the first one found will be used, but this may be changed using the builtin Web Status page.


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

## Swapping Printers

The *QLMux Proxy* will automatically find the printers on the network and add them to the printer pool. If a printer is
swapped out, the *QLMux Proxy* will automatically find the new printer and add it to the pool. The problem printer can
be left in place, just open the cover to stop it from being used.

For larger events, it may be necessary to have two pools of printers, and in this case the Web Status page will be used 
to put the new printer in the correct pool.


## Swapping RFID Readers

The *QLMux Proxy* will automatically find the RFID readers on the network and add them to the list of available RFID readers.

Best practice is to have only one RFID reader on the network at a time. If more than one RFID reader is found, the first one
will be used. If the RFID reader is swapped out, the *QLMux Proxy* will automatically find the new RFID reader and start using it.

Having the backup RFID reader powered on and not connected will make switching faster.



## Device Configuration


### Brother QL Printers
Network:
- must be on the same network as the QLMux Proxy.
- should use DHCP to get an IP address.

Printer:
- Must have a unique hostname
- Must have raster printing enabled
- for WiFi printers must have the WiFi SSID and password set 

### Impinj RFID Readers
Network:
- must be on the same network as the QLMux Proxy.
- should use DHCP to get an IP address.
- should have a unique hostname


