#!/bin/bash

set -x

#cp -v ../bin/QLLABELS.py .
#cp -v ../tests .

docker image rm -f qllabels
cd ..
docker build --no-cache -f docker-qllabels/Dockerfile -t "stuartlynne/qllabels:0.1" .

#rm -rf QLLABELS.py tests

