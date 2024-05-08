#!/bin/bash


/usr/bin/qlmuxd & 
/usr/sbin/sshd -D -o PermitEmptyPasswords=yes -o PubkeyAuthentication=no -o PermitEmptyPasswords=yes -o PrintMotd=no

#ENTRYPOINT ["/usr/sbin/sshd", "-D", "-o", 
#	"PermitEmptyPasswords=yes", "-o", "PubkeyAuthentication=no", "-o", "PermitEmptyPasswords=yes", "-o", "PrintM#otd=no" ]

#wait
#date
#echo ******************
#set -x
#touch /tmp/log
#tail -f /tmp/log


