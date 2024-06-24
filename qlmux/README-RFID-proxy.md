# RFID Proxy

## Overview

QLMux Proxy allows for discovery and connection to one or more RFID readers without
needing to know their IP addresses. This allows them to be moved around and connected as
needed, and backup readers swapped as required, without changing RaceDB configuration.

## RaceDB

RaceDB can be configured to use an RFID proxy to connect to RFID readers. 
But the current implementation only supports a single reader at the standard LLRP port (5084)

If a second reader is required then a second copy of RaceDB must be run pointing at a second
address and will also be connecting to the standard LLRP port.

To allow discovery of multiple readers via QLMux Proxy, the localhost address is used to connect
to the proxy. This works for the first reader at the standard port. 

For additional readers, an intermediate proxy is required to forward the connection to the actual
qlmux proxy. This is implemented in the `rfidproxy.py` script.

## QLMux Proxy

QLMux Proxy listens on a port and forwards connections to one or more RFID readers. It will listen
on multiple ports as configured;
  - 0.0.0.0: 5084
  - 0.0.0.0: 5084+N for as many additional readers as required.

### 1. RFID Proxy for first RFID reader

  - RaceDB connects to hostname.local:5084 (or IP address:5084)
  - QLMux Proxy 
    - listens on 0.0.0.0:5084
    - forwards do rfidhost-table:5084

N.b. this requires that RaceDB docker.env have the actual hostname or ip address.

### 2. RFID Proxy with secondary readers

Assuming there are N additional readers:

  - kiosk connects to 127.0.0.1:5084+N
  - QLMux Proxy 
    - listens on: 0.0.0.0:5084+N
    - forwards do rfidhost-kiosk1:5084
    - 

An intermediate proxy listens and forwards to the actual readers:
  127.0.0.1:5084 -> hostname:5084+N

N.b. this requires that rfidproxy.py be installed in the docker container.


