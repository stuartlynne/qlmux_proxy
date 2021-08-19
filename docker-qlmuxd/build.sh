#!/bin/bash

set -x

docker image rm -f qlmuxd
cd ..
docker build --no-cache -f docker-qlmuxd/Dockerfile -t "qlmuxd" .

