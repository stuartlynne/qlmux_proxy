#!/bin/bash

set -x
TAG="qllabels_qlmuxd:20240305a"

#docker tag qlmuxd stuartlynne/qlmuxd
docker push stuartlynne/${TAG}

