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
  OCR_WEB_SERVICE_WORKERS=1
  export OCR_WEB_SERVICE_WORKERS=1
  echo "OCR_WEB_SERVICE_WORKERS is unset -- setting to default: $OCR_WEB_SERVICE_WORKERS"
fi

if [ -z ${OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS+x} ]; then
  OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS=1
  export OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS=1
  echo "OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS is unset -- setting to default: $OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS"
fi

if [ -z ${OCR_SERVICE_WORKER_TIMEOUT+x} ]; then
  OCR_SERVICE_WORKER_TIMEOUT=1800
  echo "OCR_SERVICE_WORKER_TIMEOUT is unset -- setting to default (sec): $OCR_SERVICE_WORKER_TIMEOUT"
fi

if [ -z ${OCR_SERVICE_LOG_LEVEL+x} ]; then
  OCR_SERVICE_LOG_LEVEL=10
  echo "OCR_SERVICE_LOG_LEVEL is unset -- setting to default: $OCR_SERVICE_LOG_LEVEL"
fi

OCR_SERVICE_ACCESS_LOG_FORMAT="%(t)s [ACCESSS] %(h)s \"%(r)s\" %(s)s \"%(f)s\" \"%(a)s\""

# start the OCR_SERVICE
#
echo "Starting up OCR app using uvicorn OCR_SERVICE ..."

python_version=python3

if command -v python3.11 &>/dev/null; then
  python_version=python3.11
elif command -v python3.12 &>/dev/null; then
  python_version=python3.12
else
  echo "Neither python 3.11/3.12 are not available. Please install one of them."
fi

$python_version -m uvicorn asgi:app --host ${OCR_SERVICE_HOST:-0.0.0.0} --port ${OCR_SERVICE_PORT:-8000} --workers ${OCR_WEB_SERVICE_WORKERS:-1} --access-log
