

FROM frolvlad/alpine-python3:latest

# update and get extra utilities
RUN apk add --no-cache bash vim git less busybox-extras netcat-openbsd poppler poppler-utils dos2unix openssh 


ENV TIME_ZONE=America/Vancouver
RUN echo "qllabels.local" > /etc/hostname

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


# clone qlmux into / and copy QLLABELS.py 
#
#RUN cd / && git clone https://github.com/stuartlynne/qlmux.git 
#RUN cp /qlmux/bin/QLLABELS.py /usr/local/bin
COPY ./bin/QLLABELS.py /usr/bin
COPY ./tests /tests

# run sshd with options to limit access to racedb, no password
#
ENTRYPOINT ["/usr/sbin/sshd", "-D", "-o", "PermitEmptyPasswords=yes", "-o", "PubkeyAuthentication=no", "-o", "PermitEmptyPasswords=yes", "-o", "PrintMotd=no" ]

