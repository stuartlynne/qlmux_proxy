


#FROM python:3
#FROM frolvlad/alpine-python3:latest
FROM python:3.10.0-alpine

# update and get extra utilities
#RUN apt-get update && apt-get install -y vim less psmisc netcat-openbsd telnet libsnmp-dev pdftk ghostscript dos2unix
RUN apk add --no-cache bash vim git less busybox-extras netcat-openbsd net-snmp-dev make poppler-utils
RUN apk add --virtual build-deps gcc python3-dev musl-dev 
RUN apk add jpeg-dev zlib-dev libjpeg
RUN apk add openssh


ENV TIME_ZONE=America/Vancouver

# Set out hostname for avahi
RUN echo "qllabels.local" > /etc/hostname && \
    mkdir -p /docker-entrypoint-init.d/ 
    #mkdir -p /RaceDB && \

RUN adduser -D racedb
RUN passwd -d racedb
 

# clone qlmux into /

# get the qlmuxd.cfg into /usr/local/etc
#RUN mkdir -p /usr/local/etc
#COPY cfg/qlmuxd.cfg /usr/local/etc/qlmuxd.cfg

# net-snmp
#RUN cd /qldocker/net-snmp && ./configure --? && make && make install

# install brother_ql
#
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install Pillow
RUN python3 -m pip install brother_ql
RUN python3 -m pip install flask
RUN python3 -m pip install pysnmp-lextudio
RUN python3 -m pip install yattag

# install qlmux and support files
RUN python3 -m pip install json-cfg

# install qlmuxd and supporting files: LABELS, qlstatus, qlps2raster
#RUN set -x && cd /qlmux && make sdist install install-support
RUN cd / && git clone https://github.com/stuartlynne/qlmux_proxy.git  && ls -l /qlmux_proxy
RUN cd / && ls -ld *
RUN cd / && cd /qlmux_proxy && ls -l
RUN cd / && cd /qlmux_proxy && cat Makefile
RUN cd / && ls -ld /qlmux_proxy && cd /qlmux_proxy && cat Makefile && make sdist && make install 
RUN cd /qlmux_proxy && cat Makefile && make install-support



#ENTRYPOINT ["/bin/sh", "-c", "sleep 1000000"] ]
#ENTRYPOINT ["/bin/sh", "-c", "ssh -D -o PermitEmptyPasswords=yes -o PubkeyAuthentication=no -o PermitEmptyPasswords=yes -o PrintMotd=no"]
#ENTRYPOINT ["/bin/sh", "-c", "/usr/local/bin/race_proxy && ssh -D -o PermitEmptyPasswords=yes -o PubkeyAuthentication=no -o PermitEmptyPasswords=yes -o PrintMotd=no"]
