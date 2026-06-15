#!/bin/sh
set -e

_OPTS=" --host 0.0.0.0 --path ${CRMD_DATA_DIR:-/data}"
if [ -n "${CRMD_API_KEY}" ]; then
  _OPTS="${_OPTS} --api-key ${CRMD_API_KEY}"
fi
exec crmd serve ${_OPTS}
