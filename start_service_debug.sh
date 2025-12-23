#!/bin/bash

# set default config values
set -a
echo "Reading env vars from ./env/ocr_service.env"
source ./env/ocr_service.env
set +a

# start the OCR_SERVICE
echo "Starting up OCR app using gunicorn OCR_SERVICE ..."
echo "====================================== OCR Service Configuration =============================="
echo "OCR_SERVICE_HOST: $OCR_SERVICE_HOST"
echo "OCR_SERVICE_PORT: $OCR_SERVICE_PORT"
echo "OCR_SERVICE_WORKER_CLASS: $OCR_SERVICE_WORKER_CLASS"
echo "OCR_WEB_SERVICE_WORKERS: $OCR_WEB_SERVICE_WORKERS"
echo "OCR_SERVICE_LOG_LEVEL: $OCR_SERVICE_LOG_LEVEL"
echo "OCR_SERVICE_GUNICORN_LOG_FILE_PATH: $OCR_SERVICE_GUNICORN_LOG_FILE_PATH"
echo "OCR_SERVICE_GUNICORN_LOG_LEVEL: $OCR_SERVICE_GUNICORN_LOG_LEVEL"
echo "OCR_SERVICE_GUNICORN_MAX_REQUESTS_JITTER: $OCR_SERVICE_GUNICORN_MAX_REQUESTS_JITTER"
echo "OCR_SERVICE_GUNICORN_MAX_REQUESTS: $OCR_SERVICE_GUNICORN_MAX_REQUESTS"
echo "OCR_SERVICE_GUNICORN_TIMEOUT: $OCR_SERVICE_GUNICORN_TIMEOUT"
echo "OCR_SERVICE_GUNICORN_GRACEFUL_TIMEOUT: $OCR_SERVICE_GUNICORN_GRACEFUL_TIMEOUT"
echo "==============================================================================================="

python_version=python3

if command -v python3.11 &>/dev/null; then
  python_version=python3.11
elif command -v python3.12 &>/dev/null; then
  python_version=python3.12
elif command -v python3.13 &>/dev/null; then
  python_version=python3.13
else
  echo "Neither python 3.11/3.12/3.13/3.14 are not available. Please install one of them."
fi

$python_version -m gunicorn wsgi:app --worker-class "$OCR_SERVICE_WORKER_CLASS" \
                                     --bind "$OCR_SERVICE_HOST:$OCR_SERVICE_PORT" \
                                     --threads "1" \
                                     --workers "$OCR_WEB_SERVICE_WORKERS" \
                                     --access-logfile "$OCR_SERVICE_GUNICORN_LOG_FILE_PATH" \
                                     --reload --log-level "debug" \
                                     --max-requests "$OCR_SERVICE_GUNICORN_MAX_REQUESTS" \
                                     --max-requests-jitter "$OCR_SERVICE_GUNICORN_MAX_REQUESTS_JITTER" \
                                     --timeout "$OCR_SERVICE_GUNICORN_TIMEOUT" \
                                     --graceful-timeout "$OCR_SERVICE_GUNICORN_GRACEFUL_TIMEOUT"
