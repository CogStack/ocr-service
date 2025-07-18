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

if [ -z ${OCR_SERVICE_LOG_LEVEL+x} ]; then
  OCR_SERVICE_LOG_LEVEL=40
  echo "OCR_SERVICE_LOG_LEVEL is unset -- setting to default: $OCR_SERVICE_LOG_LEVEL"
fi

if [ -z ${OCR_WEB_SERVICE_WORKERS+x} ]; then
  OCR_WEB_SERVICE_WORKERS=1
  export OCR_WEB_SERVICE_WORKERS=1
  echo "OCR_WEB_SERVICE_WORKERS is unset -- setting to default: $OCR_WEB_SERVICE_WORKERS"
fi

if [ -z ${OCR_WEB_SERVICE_THREADS+x} ]; then
  OCR_WEB_SERVICE_THREADS=1
  export OCR_WEB_SERVICE_THREADS=1
  echo "OCR_WEB_SERVICE_THREADS is unset -- setting to default: $OCR_WEB_SERVICE_THREADS"
fi

if [ -z ${OCR_SERVICE_DEBUG_MODE+x} ]; then
  OCR_SERVICE_DEBUG_MODE=True
  export OCR_SERVICE_DEBUG_MODE=True
  echo "DEBUG_MODE is unset -- setting to default: $OCR_SERVICE_DEBUG_MODE"
fi

python3.12 -m flask run --debug --no-reload -p ${OCR_SERVICE_PORT} -h ${OCR_SERVICE_HOST}