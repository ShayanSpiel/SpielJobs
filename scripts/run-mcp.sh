#!/bin/sh
set -eu
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -n "${SPIELJOBS_PYTHON:-}" ]; then
  PYTHON="$SPIELJOBS_PYTHON"
elif [ -x "$PROJECT_DIR/.venv/bin/python" ]; then
  PYTHON="$PROJECT_DIR/.venv/bin/python"
else
  PYTHON=python3
fi
export PYTHONPATH="$PROJECT_DIR/backend${PYTHONPATH:+:$PYTHONPATH}"
exec "$PYTHON" -m spieljobs.mcp_server
