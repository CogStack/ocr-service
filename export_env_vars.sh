#!/bin/bash

set -o allexport

current_dir=$(pwd)
security_dir="../security/"

env_files=("env/general.env"
           "env/ocr_service.env"
           )

set -a

for env_file in ${env_files[@]}; do
  source $env_file
done

# for nginx vars
export DOLLAR="$"

set +a

set +o allexport