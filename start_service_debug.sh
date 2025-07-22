#!/bin/bash

# check the uvicorn config params

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

if [ -z ${OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS+x} ]; then
  OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS=1
  export OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS=1
  echo "OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS is unset -- setting to default: $OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS"
fi

if [ -z ${OCR_SERVICE_DEBUG_MODE+x} ]; then
  OCR_SERVICE_DEBUG_MODE=True
  export OCR_SERVICE_DEBUG_MODE=True
  echo "DEBUG_MODE is unset -- setting to default: $OCR_SERVICE_DEBUG_MODE"
fi

python_version=python3

if command -v python3.11 &>/dev/null; then
  python_version=python3.11
elif command -v python3.12 &>/dev/null; then
  python_version=python3.12
else
  echo "Neither python 3.11/3.12 are not available. Please install one of them."
fi

$python_version -m uvicorn asgi:app --host ${OCR_SERVICE_HOST:-0.0.0.0} --port ${OCR_SERVICE_PORT:-8000} --reload --log-level "debug"
