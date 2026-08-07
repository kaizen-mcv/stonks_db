#!/bin/bash
# Actualización diaria de Stonks DB
# Ejecutar a las 22:00 UTC (mercados cerrados)

set -e

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT/.venv"
LOG_DIR="$PROJECT/data/logs"
DATE=$(date +%Y%m%d)
LOG="$LOG_DIR/daily_update_${DATE}.log"

mkdir -p "$LOG_DIR"

source "$VENV/bin/activate"
cd "$PROJECT"

echo "=== Stonks daily update $(date) ===" >> "$LOG"

# 1. Precios equity (solo último año para update)
echo "[$(date +%H:%M)] Actualizando precios equity..." >> "$LOG"
stonks equity fetch --batch global --period 1y >> "$LOG" 2>&1 || true

# 2. Índices de mercado
echo "[$(date +%H:%M)] Actualizando índices..." >> "$LOG"
stonks index fetch --period 1y >> "$LOG" 2>&1 || true

# 3. ETFs
echo "[$(date +%H:%M)] Actualizando ETFs..." >> "$LOG"
stonks fund fetch --period 1y >> "$LOG" 2>&1 || true

# 4. Commodities
echo "[$(date +%H:%M)] Actualizando commodities..." >> "$LOG"
stonks commodity fetch --period 1y >> "$LOG" 2>&1 || true

# 5. Forex ECB + yfinance OHLC
echo "[$(date +%H:%M)] Actualizando forex..." >> "$LOG"
stonks forex fetch >> "$LOG" 2>&1 || true
stonks forex fetch-yf --period 1y >> "$LOG" 2>&1 || true

# 6. Crypto (CoinGecko + yfinance)
echo "[$(date +%H:%M)] Actualizando crypto..." >> "$LOG"
stonks crypto fetch --days 30 >> "$LOG" 2>&1 || true
stonks crypto fetch-yf --period 1y >> "$LOG" 2>&1 || true

# 7. Yields y spreads (FRED)
echo "[$(date +%H:%M)] Actualizando FRED..." >> "$LOG"
stonks macro fetch --source fred >> "$LOG" 2>&1 || true

# 8. Bonos y ratings soberanos
echo "[$(date +%H:%M)] Actualizando bonos FI..." >> "$LOG"
stonks fi bonds >> "$LOG" 2>&1 || true
stonks fi ratings >> "$LOG" 2>&1 || true

# 9. VIX / sentimiento
echo "[$(date +%H:%M)] Actualizando sentimiento..." >> "$LOG"
stonks alt fetch --period 1y >> "$LOG" 2>&1 || true

# 10. Volatilidad y futuros (v0.4.0)
echo "[$(date +%H:%M)] Actualizando volatilidad..." >> "$LOG"
stonks deriv vol-fetch --period 1y >> "$LOG" 2>&1 || true

echo "[$(date +%H:%M)] Actualizando futuros..." >> "$LOG"
stonks deriv futures-fetch --period 1y >> "$LOG" 2>&1 || true

# 11. Intraday 1h — todos los dominios (v0.4.0)
echo "[$(date +%H:%M)] Intraday 1h crypto..." >> "$LOG"
stonks intraday fetch -d crypto -i 1h >> "$LOG" 2>&1 || true

echo "[$(date +%H:%M)] Intraday 1h forex..." >> "$LOG"
stonks intraday fetch -d forex -i 1h >> "$LOG" 2>&1 || true

echo "[$(date +%H:%M)] Intraday 1h commodity..." >> "$LOG"
stonks intraday fetch -d commodity -i 1h >> "$LOG" 2>&1 || true

echo "[$(date +%H:%M)] Intraday 1h equity (top 5000)..." >> "$LOG"
stonks intraday fetch -d equity -i 1h -n 5000 >> "$LOG" 2>&1 || true

# 12. Posicionamiento COT (la CFTC publica los viernes)
echo "[$(date +%H:%M)] Actualizando COT..." >> "$LOG"
stonks deriv cot-fetch >> "$LOG" 2>&1 || true

# 13. Pipeline daily (analyst, options, pipeline steps)
#     Incluye la construccion de gold al final: antes habia un
#     segundo cron a las 21:30 que hacia lo mismo en paralelo y
#     competia por los locks de este.
echo "[$(date +%H:%M)] Pipeline daily..." >> "$LOG"
stonks update -c daily >> "$LOG" 2>&1 || true

echo "[$(date +%H:%M)] === Update completado ===" >> "$LOG"
