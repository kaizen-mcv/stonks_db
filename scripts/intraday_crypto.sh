#!/bin/bash
# Intraday crypto 24/7 (fines de semana)
# Cron: */5 * * * 0,6  .../scripts/intraday_crypto.sh

set -e

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT/.venv"
LOG_DIR="$PROJECT/data/logs"
DATE=$(date +%Y%m%d)
LOG="$LOG_DIR/intraday_crypto_${DATE}.log"

mkdir -p "$LOG_DIR"

source "$VENV/bin/activate"
cd "$PROJECT"

TS=$(date +%H:%M:%S)
echo "[$TS] Intraday 1m crypto (weekend)" >> "$LOG"
stonks intraday fetch -d crypto -i 1m >> "$LOG" 2>&1 || true
