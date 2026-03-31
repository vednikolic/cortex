#!/usr/bin/env bash
# reflect-prep.sh: Generate reflect-context.json for /reflect consumption.
# Thin wrapper around cortex_lib/reflect_prep.py.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "${SCRIPT_DIR}/concepts" reflect-prep "$@"
