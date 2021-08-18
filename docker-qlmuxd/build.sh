#!/bin/bash

set -x

docker image rm -f qlmuxd
cd ..
docker build -f docker-qlmuxd/Dockerfile -t "qlmuxd" .

