#!/bin/bash

# if ran manually execute "export_env_vars.sh"

# start the OCR_SERVICE
echo "Starting up OCR app using gunicorn OCR_SERVICE ..."
echo "====================================== OCR Service Configuration =============================="
echo "OCR_SERVICE_HOST: $OCR_SERVICE_HOST"
echo "OCR_SERVICE_PORT: $OCR_SERVICE_PORT"
echo "OCR_WEB_SERVICE_WORKERS: $OCR_WEB_SERVICE_WORKERS"
echo "OCR_WEB_SERVICE_THREADS: $OCR_WEB_SERVICE_THREADS"
echo "OCR_SERVICE_LOG_LEVEL: $OCR_SERVICE_LOG_LEVEL"
echo "OCR_SERVICE_GUNICORN_LOG_LEVEL: $OCR_SERVICE_GUNICORN_LOG_LEVEL"
echo "==============================================================================================="

python_version=python3

if command -v python3.11 &>/dev/null; then
  python_version=python3.11
elif command -v python3.12 &>/dev/null; then
  python_version=python3.12
else
  echo "Neither python 3.11/3.12 are not available. Please install one of them."
fi

$python_version -m gunicorn wsgi:app --worker-class sync --bind "$OCR_SERVICE_HOST:$OCR_SERVICE_PORT" --threads "$OCR_WEB_SERVICE_THREADS"  --workers "$OCR_WEB_SERVICE_WORKERS"  --access-logfile "./log/ocr_service.log" --log-level "$OCR_SERVICE_GUNICORN_LOG_LEVEL"
