#!/bin/bash
#

apis=' https://ajax.googleapis.com/ajax/libs/jquery/3.5.1/jquery.min.js \
	https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js'

for api in ${apis} ; do
	wget "${api}"
done
