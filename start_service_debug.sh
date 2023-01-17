#!/bin/bash

# check the gunicorn config params
#
if [ -z ${OCR_SERVICE_HOST+x} ]; then
  OCR_SERVICE_HOST=0.0.0.0
  echo "OCR_SERVICE_HOST is unset -- setting to default: $OCR_SERVICE_HOST"
fi

if [ -z ${OCR_SERVICE_PORT+x} ]; then
  OCR_SERVICE_PORT=8090
  echo "OCR_SERVICE_PORT is unset -- setting to default: $OCR_SERVICE_PORT"
fi

python3.11 -m flask run --no-debugger --no-reload -p ${OCR_SERVICE_PORT}