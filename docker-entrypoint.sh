#!/bin/sh
set -e

exec crmd serve \
  --host 0.0.0.0 \
  --api-key "${CRMD_API_KEY}" \
  --path "${CRMD_DATA_DIR:-/data}"
