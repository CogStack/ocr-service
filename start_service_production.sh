#!/bin/bash

# set default config values
set -a
echo "Reading env vars from ./env/ocr_service.env"
source ./env/ocr_service.env
set +a

# start the OCR_SERVICE
echo "Starting up OCR app using uvicorn OCR_SERVICE ..."
echo "====================================== OCR Service Configuration =============================="
echo "OCR_SERVICE_HOST: $OCR_SERVICE_HOST"
echo "OCR_SERVICE_PORT: $OCR_SERVICE_PORT"
echo "OCR_WEB_SERVICE_WORKERS: $OCR_WEB_SERVICE_WORKERS"
echo "OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS: $OCR_WEB_SERVICE_LIMIT_CONCURRENCY_TASKS"
echo "OCR_SERVICE_WORKER_TIMEOUT: $OCR_SERVICE_WORKER_TIMEOUT"
echo "OCR_SERVICE_LOG_LEVEL: $OCR_SERVICE_LOG_LEVEL"
echo "OCR_SERVICE_UVICORN_LOG_LEVEL: $OCR_SERVICE_UVICORN_LOG_LEVEL"
echo "==============================================================================================="

python_version=python3

if command -v python3.11 &>/dev/null; then
  python_version=python3.11
elif command -v python3.12 &>/dev/null; then
  python_version=python3.12
else
  echo "Neither python 3.11/3.12 are not available. Please install one of them."
fi

$python_version -m uvicorn asgi:app --host "$OCR_SERVICE_HOST" --port "$OCR_SERVICE_PORT" --workers "$OCR_WEB_SERVICE_WORKERS" --access-log --log-level "$OCR_SERVICE_UVICORN_LOG_LEVEL"
