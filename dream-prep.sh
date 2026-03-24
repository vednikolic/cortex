#!/usr/bin/env bash
# dream-prep.sh: Generate dream-context.json for /dream consumption.
# Thin wrapper around cortex_lib/dream_prep.py.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "${SCRIPT_DIR}/concepts" dream-prep "$@"
