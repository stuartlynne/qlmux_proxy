#!/bin/bash

set -x

docker image rm -f qlmuxd
docker build -t "qlmuxd" .

