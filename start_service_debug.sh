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

python3 -m flask run --no-debugger --no-reload -p ${SERVICE_PORT}