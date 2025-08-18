#!/bin/bash

# Enable strict mode (without -e to avoid exit-on-error)
set -uo pipefail

echo "🔧 Running $(basename "$0")..."

set -a

current_dir=$(pwd)
env_dir="./env/"

env_files=("env/general.env"
           "env/ocr_service.env"
          )

for env_file in "${env_files[@]}"; do
  if [ -f "$env_file" ]; then
    echo "✅ Sourcing $env_file"
    # shellcheck disable=SC1090
    source "$env_file"
  else
    echo "⚠️ Skipping missing env file: $env_file"
  fi
done

# For nginx vars / Docker Compose templating support
export DOLLAR="$"

# Disable auto-export
set +a

# Restore safe defaults for interactive/dev shell
set +u
set +o pipefail