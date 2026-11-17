#!/bin/bash
set -eu
project_dir="$(cd "$(dirname "$0")/.." && pwd)"
python_bin="${SPIELJOBS_PYTHON:-$project_dir/.venv/bin/python}"
listeners="$(lsof -nP -tiTCP:8000 -sTCP:LISTEN 2>/dev/null || true)"
for pid in $listeners; do
  command_line="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  case "$command_line" in
    *uvicorn*spieljobs.server:app*)
      printf 'Stopping previous SpielJobs backend (PID %s).\n' "$pid"
      kill "$pid"
      ;;
    *)
      printf 'Port 8000 is in use by PID %s: %s\n' "$pid" "$command_line" >&2
      printf 'Leaving that process untouched. Stop it or choose another port.\n' >&2
      exit 1
      ;;
  esac
done
for attempt in 1 2 3 4 5; do
  if ! lsof -nP -tiTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then break; fi
  sleep 1
done
cd "$project_dir"
exec env PYTHONPATH="$project_dir/backend" "$python_bin" -m uvicorn spieljobs.server:app --host 127.0.0.1 --port 8000
