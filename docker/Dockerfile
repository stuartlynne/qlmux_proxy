


#FROM python:3
#FROM frolvlad/alpine-python3:latest
FROM python:3.10.0-alpine

# update and get extra utilities
#RUN apt-get update && apt-get install -y vim less psmisc netcat-openbsd telnet libsnmp-dev pdftk ghostscript dos2unix
RUN apk add --no-cache bash vim git less busybox-extras netcat-openbsd net-snmp-dev make poppler-utils
RUN apk add --virtual build-deps gcc python3-dev musl-dev 
RUN apk add jpeg-dev zlib-dev libjpeg

# install openssh and generate keys
RUN apk add openssh
RUN ssh-keygen -A


ENV TIME_ZONE=America/Vancouver

# Set out hostname for avahi
#RUN echo "qllabels.local" > /etc/hostname && 
#mkdir -p /docker-entrypoint-init.d/ 

RUN adduser -D racedb
RUN passwd -d racedb

RUN python3 -m pip install --upgrade pip

# Pillow is a dependency of brother_ql, but does not install properly via setup.py
RUN python3 -m pip install Pillow

# the pypi version of brother_ql is out of date, so we need to install from github
RUN cd / && git clone https://github.com/pklaus/brother_ql.git
RUN cd /brother_ql && python3 setup.py install

# install qllabels, 
RUN cd / && git clone https://github.com/stuartlynne/qllabels.git 
RUN cd /qllabels && make install 

# pysnmp-lextudio is the current version of pysnmp, supports SNMP broadcast 
# it does not install properly via setup.py
RUN python3 -m pip install pysnmp-lextudio

# install qlmux_proxy
RUN cd / && git clone https://github.com/stuartlynne/qlmux_proxy.git 
RUN cd /qlmux_proxy && make install 

# two entry points, one for the proxy, one for the sshd
ENTRYPOINT ["/bin/sh", "-c", "/usr/sbin/sshd -D -p 9122 -o PermitEmptyPasswords=yes -o PubkeyAuthentication=no -o PermitEmptyPasswords=yes -o PrintMotd=no & race_proxy"]

