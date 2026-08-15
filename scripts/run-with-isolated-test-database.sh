#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 3 ]; then
  echo "usage: $0 DATABASE_ROOT PYTHON COMMAND [ARG ...]" >&2
  exit 2
fi

database_root="$1"
database_python="$2"
shift 2

mkdir -p "$database_root"
database_root="$(cd "$database_root" && pwd -P)"
database_run_dir="$(mktemp -d "$database_root/database.XXXXXX")"
database_path="$database_run_dir/test.sqlite"
database_cleaned=0
child_pid=""

cleanup_database() {
  if [ "$database_cleaned" -eq 1 ]; then
    return
  fi
  database_cleaned=1
  rm -f \
    "$database_path" \
    "$database_path-wal" \
    "$database_path-shm" \
    "$database_path-journal"
  rmdir "$database_run_dir" 2>/dev/null || true
}

forward_signal() {
  local signal_name="$1"
  local signal_status="$2"
  trap - INT TERM HUP
  if [ -n "$child_pid" ] && kill -0 "$child_pid" 2>/dev/null; then
    kill -s "$signal_name" -- "-$child_pid" 2>/dev/null || \
      kill -s "$signal_name" "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  child_pid=""
  exit "$signal_status"
}

managed_launcher='import os, signal, sys
signal.signal(signal.SIGINT, signal.SIG_DFL)
signal.signal(signal.SIGTERM, signal.SIG_DFL)
signal.signal(signal.SIGHUP, signal.SIG_DFL)
os.setsid()
os.execvp(sys.argv[1], sys.argv[1:])'

run_managed_command() {
  "$database_python" -c "$managed_launcher" "$@" &
  child_pid=$!
  set +e
  wait "$child_pid"
  local managed_status=$?
  set -e
  child_pid=""
  return "$managed_status"
}

trap cleanup_database EXIT
trap 'forward_signal INT 130' INT
trap 'forward_signal TERM 143' TERM
trap 'forward_signal HUP 129' HUP

export DATABASE_URL="sqlite:///$database_path"
echo "Isolated test database: $database_path"

init_status=0
run_managed_command \
  "$database_python" -c \
  "from src.database.models import init_db; init_db()" || init_status=$?
if [ "$init_status" -ne 0 ]; then
  exit "$init_status"
fi

command_status=0
run_managed_command "$@" || command_status=$?
exit "$command_status"
