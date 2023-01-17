#!/bin/bash

# check the gunicorn config params
#
if [ -z ${SERVICE_HOST+x} ]; then
  SERVICE_HOST=0.0.0.0
  echo "SERVICE_HOST is unset -- setting to default: $SERVICE_HOST"
fi

if [ -z ${SERVICE_PORT+x} ]; then
  SERVICE_PORT=8090
  echo "SERVICE_PORT is unset -- setting to default: $SERVICE_PORT"
fi

if [ -z ${SERVICE_WORKERS+x} ]; then
  SERVICE_WORKERS=1
  echo "SERVICE_WORKERS is unset -- setting to default: $SERVICE_WORKERS"
fi

if [ -z ${SERVICE_THREADS+x} ]; then
  SERVICE_THREADS=1
  echo "SERVICE_THREADS is unset -- setting to default: $SERVICE_THREADS"
fi

if [ -z ${SERVICE_WORKER_TIMEOUT+x} ]; then
  SERVICE_WORKER_TIMEOUT=300
  echo "SERVICE_WORKER_TIMEOUT is unset -- setting to default (sec): $SERVICE_WORKER_TIMEOUT"
fi

SERVER_ACCESS_LOG_FORMAT="%(t)s [ACCESSS] %(h)s \"%(r)s\" %(s)s \"%(f)s\" \"%(a)s\""

# start the server
#
echo "Starting up Flask app using gunicorn server ..."
gunicorn --bind $SERVER_HOST:$SERVER_PORT --workers=$SERVER_WORKERS --threads=$SERVER_THREADS --timeout=$SERVER_WORKER_TIMEOUT \
  --access-logformat="$SERVER_ACCESS_LOG_FORMAT" --access-logfile=- --log-file=- --log-level info \
  wsgi
  
python3.11 -m flask run --no-debugger --no-reload -p $SERVICE_PORT