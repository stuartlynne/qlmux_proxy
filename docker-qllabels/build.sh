#!/bin/bash

set -x

cp -v ../bin/QLLABELS.py .
docker image rm -f qllabels
docker build -t "stuartlynne/qllabels:0.1" .

