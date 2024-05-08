


#FROM python:3
FROM frolvlad/alpine-python3:latest

# update and get extra utilities
RUN apk add --no-cache bash vim git less busybox-extras netcat-openbsd make poppler poppler-utils dos2unix openssh 
RUN apk add --virtual build-deps gcc python3-dev musl-dev 
RUN apk add jpeg-dev zlib-dev libjpeg net-snmp-dev


ENV TIME_ZONE=America/Vancouver

# Set out hostname for avahi
RUN echo "qlmuxd.local" > /etc/hostname && \
    mkdir -p /RaceDB && \
    mkdir -p /docker-entrypoint-init.d/ 

RUN adduser -D racedb
RUN passwd -d racedb
RUN ssh-keygen -A
# these are required for pillow to be built (brother_ql requirement)
RUN apk add --virtual build-deps gcc python3-dev musl-dev
RUN apk add jpeg-dev zlib-dev libjpeg 

# pdf2image, pillow and brother_ql
RUN python3 -m pip install --upgrade pip && \
     python3 -m pip install json-cfg && \
     python3 -m pip install pdf2image && \
     python3 -m pip install pillow && \
     python3 -m pip install brother_ql
 
COPY fonts/Helvetica.ttf /usr/share/fonts/truetype/Helvetica.ttf
COPY bin/QLLABELS.py bin/qlstatus /usr/bin/
COPY docker-qlmuxd/entrypoint.sh /entrypoint.sh

# clone qlmux into /
RUN cd / && git clone https://github.com/stuartlynne/qlmux.git 
RUN cd /qlmux && make sdist install 

# get the qlmuxd.cfg into /usr/local/etc
RUN mkdir -p /usr/local/etc
COPY cfg/qlmuxd.cfg cfg/qllabels.cfg /usr/local/etc/

ENTRYPOINT ["/entrypoint.sh"]

