#!/usr/bin/env bash
# Runs a self-contained PostgreSQL cluster for local development, owned by the
# current user (no sudo needed). Data lives in ./.pgdata at the repo root.
#
#   scripts/dev-postgres.sh start   # init (first run) + start on port 5433
#   scripts/dev-postgres.sh stop
#   scripts/dev-postgres.sh status
#
# Creates databases `reschatbot` and `reschatbot_test`, owned by role
# `reschat` with password `reschat` (development only - never use in prod).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PGDATA="${PGDATA:-$ROOT/.pgdata}"
PGPORT="${PGPORT:-5433}"
PGUSER_NAME="reschat"
PGPASS="reschat"

find_bin() {
  if command -v pg_ctl >/dev/null 2>&1; then dirname "$(command -v pg_ctl)"; return; fi
  local d
  d=$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | sort -V | tail -1 || true)
  if [[ -n "$d" ]]; then echo "$d"; return; fi
  echo "PostgreSQL server binaries (initdb/pg_ctl) not found" >&2; exit 1
}
BIN="$(find_bin)"

cmd="${1:-start}"
case "$cmd" in
  start)
    if [[ ! -f "$PGDATA/PG_VERSION" ]]; then
      echo "Initialising cluster in $PGDATA"
      pwfile="$(mktemp)"; echo "$PGPASS" > "$pwfile"
      "$BIN/initdb" -D "$PGDATA" -U "$PGUSER_NAME" --pwfile="$pwfile" \
        --auth-local=scram-sha-256 --auth-host=scram-sha-256 -E UTF8 >/dev/null
      rm -f "$pwfile"
    fi
    if "$BIN/pg_ctl" -D "$PGDATA" status >/dev/null 2>&1; then
      echo "Already running on port $PGPORT"
    else
      "$BIN/pg_ctl" -D "$PGDATA" -l "$PGDATA/server.log" -w \
        -o "-p $PGPORT -k $PGDATA -c listen_addresses=127.0.0.1" start
    fi
    for db in reschatbot reschatbot_test; do
      PGPASSWORD="$PGPASS" psql -h 127.0.0.1 -p "$PGPORT" -U "$PGUSER_NAME" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname='$db'" | grep -q 1 || \
        PGPASSWORD="$PGPASS" psql -h 127.0.0.1 -p "$PGPORT" -U "$PGUSER_NAME" -d postgres -qc "CREATE DATABASE $db"
    done
    echo "DATABASE_URL=postgresql+psycopg://$PGUSER_NAME:$PGPASS@127.0.0.1:$PGPORT/reschatbot"
    ;;
  stop) "$BIN/pg_ctl" -D "$PGDATA" -w stop ;;
  status) "$BIN/pg_ctl" -D "$PGDATA" status ;;
  *) echo "usage: $0 {start|stop|status}" >&2; exit 2 ;;
esac
