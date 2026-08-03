#!/bin/bash
# Actualización intraday de alta frecuencia
# Ejecutar cada 5 min (1m) o cada hora (5m)
#
# Uso:
#   intraday_update.sh 1m   # top 500 equity + crypto + forex majors
#   intraday_update.sh 5m   # top 5000 equity + todos crypto/forex/commodity
#
# Cron recomendado (crontab -e):
#   */5 * * * 1-5  .../scripts/intraday_update.sh 1m   # L-V cada 5 min
#   */5 * * * 0,6  .../scripts/intraday_crypto.sh 1m   # S-D solo crypto
#   0 * * * 1-5    .../scripts/intraday_update.sh 5m   # L-V cada hora

set -e

INTERVAL="${1:-1m}"

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT/.venv"
LOG_DIR="$PROJECT/data/logs"
DATE=$(date +%Y%m%d)
LOG="$LOG_DIR/intraday_${INTERVAL}_${DATE}.log"

mkdir -p "$LOG_DIR"

source "$VENV/bin/activate"
cd "$PROJECT"

TS=$(date +%H:%M:%S)

if [ "$INTERVAL" = "1m" ]; then
    # 1m: solo los más líquidos (7 días retención)
    echo "[$TS] Intraday 1m equity top 500" >> "$LOG"
    stonks intraday fetch -d equity -i 1m -n 500 >> "$LOG" 2>&1 || true

    echo "[$TS] Intraday 1m crypto" >> "$LOG"
    stonks intraday fetch -d crypto -i 1m >> "$LOG" 2>&1 || true

    echo "[$TS] Intraday 1m forex" >> "$LOG"
    stonks intraday fetch -d forex -i 1m >> "$LOG" 2>&1 || true

elif [ "$INTERVAL" = "5m" ]; then
    # 5m: más amplio (6 meses retención)
    echo "[$TS] Intraday 5m equity top 5000" >> "$LOG"
    stonks intraday fetch -d equity -i 5m -n 5000 >> "$LOG" 2>&1 || true

    echo "[$TS] Intraday 5m crypto" >> "$LOG"
    stonks intraday fetch -d crypto -i 5m >> "$LOG" 2>&1 || true

    echo "[$TS] Intraday 5m forex" >> "$LOG"
    stonks intraday fetch -d forex -i 5m >> "$LOG" 2>&1 || true

    echo "[$TS] Intraday 5m commodity" >> "$LOG"
    stonks intraday fetch -d commodity -i 5m >> "$LOG" 2>&1 || true
fi
