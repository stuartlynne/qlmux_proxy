


FROM python:3

# update and get extra utilities
RUN apt-get update && apt-get install -y vim less psmisc netcat-openbsd telnet libsnmp-dev pdftk ghostscript dos2unix

ENV TIME_ZONE=America/Vancouver

# Set out hostname for avahi
RUN echo "qlmuxd.local" > /etc/hostname && \
    mkdir -p /RaceDB && \
    mkdir -p /docker-entrypoint-init.d/ && \
    useradd -m -s /bin/bash racedb

# clone qlmux into /
RUN cd / && git clone https://github.com/stuartlynne/qlmux.git 

# get the qlmuxd.cfg into /usr/local/etc
RUN mkdir -p /usr/local/etc
COPY cfg/qlmuxd.cfg /usr/local/etc/qlmuxd.cfg

# net-snmp
#RUN cd /qldocker/net-snmp && ./configure --? && make && make install

# install brother_ql
#
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install brother_ql

# install qlmux and support files
RUN python3 -m pip install json-cfg

# install qlmuxd and supporting files: LABELS, qlstatus, qlps2raster
RUN cd /qlmux && make sdist install install-support


ENTRYPOINT ["/usr/local/bin/qlmuxd"]
