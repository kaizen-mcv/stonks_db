#!/bin/bash
# Actualización diaria de Stonks DB
# Ejecutar a las 22:00 UTC (mercados cerrados)

set -e

VENV="/home/marc/Projects/db-projects/stonks/.venv"
PROJECT="/home/marc/Projects/db-projects/stonks"
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

# 5. Forex ECB (últimos 90 días)
echo "[$(date +%H:%M)] Actualizando forex..." >> "$LOG"
stonks forex fetch >> "$LOG" 2>&1 || true

# 6. Crypto
echo "[$(date +%H:%M)] Actualizando crypto..." >> "$LOG"
stonks crypto fetch --days 30 >> "$LOG" 2>&1 || true

# 7. Yields y spreads (FRED)
echo "[$(date +%H:%M)] Actualizando FRED..." >> "$LOG"
stonks macro fetch --source fred >> "$LOG" 2>&1 || true

# 8. VIX / sentimiento
echo "[$(date +%H:%M)] Actualizando sentimiento..." >> "$LOG"
stonks alt fetch --period 1y >> "$LOG" 2>&1 || true

echo "[$(date +%H:%M)] === Update completado ===" >> "$LOG"
