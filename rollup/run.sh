#!/usr/bin/env bash
# Nightly rollup wrapper, run by cron at 02:45. At that hour the previous calendar
# day holds the full study day, so we roll up yesterday.
#
# The ingest URL is read from rollup/.env (gitignored). Until Phase 2 stands up the
# real API Gateway, leave it unset: the job still runs nightly and writes the daily
# rollup to rollup/out/, it just does not POST anywhere yet.
set -euo pipefail

REPO="/home/donaldraph/builds/study-conscience"
cd "$REPO"

# Optional config: INGEST_URL, INGEST_TOKEN
if [ -f rollup/.env ]; then
  # shellcheck disable=SC1091
  set -a; . rollup/.env; set +a
fi

DAY="$(date -d 'yesterday' +%F)"
OUT="rollup/out/${DAY}.json"

ARGS=(--date "$DAY" --out "$OUT")
if [ -n "${INGEST_URL:-}" ]; then
  ARGS+=(--ingest-url "$INGEST_URL")
  [ -n "${INGEST_TOKEN:-}" ] && ARGS+=(--ingest-token "$INGEST_TOKEN")
fi

echo "[$(date -Iseconds)] rolling up ${DAY}"
python3 -m rollup.rollup "${ARGS[@]}"
echo "[$(date -Iseconds)] done"
