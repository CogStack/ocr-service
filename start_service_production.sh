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

if [ -z ${OCR_WEB_SERVICE_WORKERS+x} ]; then
  OCR_WEB_SERVICE_WORKERS=4
  export OCR_WEB_SERVICE_WORKERS=4
  echo "OCR_WEB_SERVICE_WORKERS is unset -- setting to default: $OCR_WEB_SERVICE_WORKERS"
fi

if [ -z ${OCR_WEB_SERVICE_THREADS+x} ]; then
  OCR_WEB_SERVICE_THREADS=1
  export OCR_WEB_SERVICE_THREADS=1
  echo "OCR_WEB_SERVICE_THREADS is unset -- setting to default: $OCR_WEB_SERVICE_THREADS"
fi

if [ -z ${OCR_SERVICE_WORKER_TIMEOUT+x} ]; then
  OCR_SERVICE_WORKER_TIMEOUT=1800
  echo "OCR_SERVICE_WORKER_TIMEOUT is unset -- setting to default (sec): $OCR_SERVICE_WORKER_TIMEOUT"
fi

if [ -z ${OCR_SERVICE_LOG_LEVEL+x} ]; then
  OCR_SERVICE_LOG_LEVEL=10
  echo "OCR_SERVICE_LOG_LEVEL is unset -- setting to default: $OCR_SERVICE_LOG_LEVEL"
fi

if [ -z ${OCR_WEB_SERVICE_WORKER_CLASS+x} ]; then
  OCR_WEB_SERVICE_WORKER_CLASS="sync"
  echo "OCR_WEB_SERVICE_WORKER_CLASS is unset -- setting to default: $OCR_WEB_SERVICE_WORKER_CLASS"
fi

OCR_SERVICE_ACCESS_LOG_FORMAT="%(t)s [ACCESSS] %(h)s \"%(r)s\" %(s)s \"%(f)s\" \"%(a)s\""

# start the OCR_SERVICE
#
echo "Starting up Flask app using gunicorn OCR_SERVICE ..."
python3.12 -m gunicorn --bind $OCR_SERVICE_HOST:$OCR_SERVICE_PORT -w $OCR_WEB_SERVICE_WORKERS --threads=$OCR_WEB_SERVICE_THREADS --timeout=$OCR_SERVICE_WORKER_TIMEOUT \
  --access-logformat="$OCR_SERVICE_ACCESS_LOG_FORMAT" --access-logfile=./ocr_service.log --log-file=./ocr_service.log --log-level 'error' --worker-class=$OCR_WEB_SERVICE_WORKER_CLASS \
  wsgi