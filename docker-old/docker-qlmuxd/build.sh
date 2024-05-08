#!/bin/bash

TAG="stuartlynne/qllabels_qlmuxd:20240305d"

set -x
cd ..

docker image rm -f qllabels_qlmuxd
docker image rm -f ${TAG}
docker build --no-cache -f docker-qlmuxd/Dockerfile -t "${TAG}" . || exit 1
docker push ${TAG}

