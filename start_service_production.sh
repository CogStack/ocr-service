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

# prefer the venv if available (in docker container or virtual environment)
VIRTUAL_ENV=${VIRTUAL_ENV:-/opt/venv}
if [[ -x "$VIRTUAL_ENV/bin/gunicorn" ]]; then
  export VIRTUAL_ENV
  export PATH="$VIRTUAL_ENV/bin:$PATH"
  python_cmd="$VIRTUAL_ENV/bin/python"
  gunicorn_cmd="$VIRTUAL_ENV/bin/gunicorn"
else
  # Fallback to system python if venv missing
  python_cmd=python3
  if command -v python3.12 &>/dev/null; then
    python_cmd=python3.12
  elif command -v python3.11 &>/dev/null; then
    python_cmd=python3.11
  fi
  gunicorn_cmd="$python_cmd -m gunicorn"
fi

exec $gunicorn_cmd wsgi:app --worker-class "$OCR_SERVICE_WORKER_CLASS" --bind "$OCR_SERVICE_HOST:$OCR_SERVICE_PORT" --threads "$OCR_WEB_SERVICE_THREADS"  --workers "$OCR_WEB_SERVICE_WORKERS"  --access-logfile "./log/ocr_service.log" --log-level "$OCR_SERVICE_GUNICORN_LOG_LEVEL"
