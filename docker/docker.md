# QLMux Proxy Docker Setup - Host

Running the QLMux Proxy in a container is a convienent way to run the proxy without having to install any dependencies on your host machine. 

This document describes how to run the QLMux Proxy in a container using the host network. This is the simplest way to run the container, and is equivlent to running the QLMux Proxy on the host machine itself but without having 
to install any dependencies on the host machine.

The QLMux Proxy is to support *RaceDB* for:

- printing Frame and bib labels on Brother QL label printers
- finding and connecting to Impinj RFID reader for passive tag reading and encoding

The container contains three services:
- qlmux-proxy
    - the service that uses SNMP Broadcast discovery to find Brother QL printers and Impinj RFID readers
    - the qlmuxd service that sets up pools of printers
    - the tcpproxy service that forwards the RaceDB connection to the Impinj Reader
    - a webstatus page
- qllabels
    - a simple script that converts the PDF label files to the Brother QL format and sends them to the qlmux-proxy
- sshd
    - allows access to the container via ssh to run the qllabels file from RaceDB

## Network Configuration - Host

The container needs to run with host networking. This is because the qlmux-proxy uses SNMP broadcast to find the printers and readers. 

Currently the following ports are used by the container:
- 9101-9103 - qlmux-proxy uses these to get printing jobs for the large or small printers
- 9180 - qlmux-proxy web status page
- 9122 - sshd access

## RaceDB Configuration

RaceDB needs to have be configured in two ways:

1. docker.env

Add the following lines to the docker.env file to point RaceDB
at the correct host that is running the qlmux_proxy container.

```
# Impinj R1000 with Lilly 5dBi PCB UHF RFID Patch antenna wands
export RFID_READER_HOST=YOURHOSTNAME.local
export RFID_TRANSMIT_POWER_8080=40
export RFID_RECEIVER_SENSITIVITY_8080=20

```

2. RaceDB needs to know how to access the qllabels program.

This can be done either by using ssh to call into the qlmux_proxy container to run
the qllabels program, or by installing the qllabels program in the RaceDB container.

In the RaceDB systeminfo add the following to the "Cmd use to print Bib Tag (parameter is the PDF file)
```
ssh -p 9122 -o StrictHostKeyChecking=no racedb@YOURHOSTNAME.local qllabels "$1" 2> /dev/null
```







