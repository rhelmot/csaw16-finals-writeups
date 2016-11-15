#!/bin/bash
if [ -z "$1" ]; then
  rm -f mitm-recv.log mitm-send.log
  touch mitm-recv.log
  touch mitm-send.log
  ./client.py parse mitm-send.log mitm-recv.log &
  socat OPENSSL-LISTEN:8080,bind=0.0.0.0,reuseaddr,cert=socat.crt,key=socat.key,verify=0 EXEC:"./mitm.sh x"
  kill %
  killall openssl
else
  exec tee mitm-send.log | openssl s_client -connect reversing.chal.csaw.io:1348 -quiet | tee mitm-recv.log
fi
