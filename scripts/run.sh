#!/usr/bin/env bash
# Daily pipeline wrapper for cron. Usage: scripts/run.sh [since_days]
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data
source .venv/bin/activate
echo "=== run $(date -u +%FT%TZ) ==="
python -m deals_vectoriser.run --since-days "${1:-2}"
