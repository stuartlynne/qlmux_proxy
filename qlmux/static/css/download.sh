#!/bin/bash
#

apis='https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css'

for api in ${apis} ; do
	wget "${api}"
done
