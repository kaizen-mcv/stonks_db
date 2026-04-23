#!/bin/bash
# Actualización semanal (datos menos frecuentes)
# Ejecutar domingos a las 10:00

set -e

PROJECT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$PROJECT/.venv"
LOG_DIR="$PROJECT/data/logs"
DATE=$(date +%Y%m%d)
LOG="$LOG_DIR/weekly_update_${DATE}.log"

mkdir -p "$LOG_DIR"

source "$VENV/bin/activate"
cd "$PROJECT"

echo "=== Stonks weekly update $(date) ===" >> "$LOG"

# 1. Macro World Bank (datos anuales)
echo "[$(date +%H:%M)] Actualizando macro WB..." >> "$LOG"
stonks macro fetch --source world_bank >> "$LOG" 2>&1 || true

# 2. Perfiles de país y demografía
echo "[$(date +%H:%M)] Actualizando países..." >> "$LOG"
stonks country fetch >> "$LOG" 2>&1 || true

# 3. Fundamentales (income, balance, CF, divs)
echo "[$(date +%H:%M)] Actualizando fundamentales..." >> "$LOG"
stonks equity fundamentals --all >> "$LOG" 2>&1 || true

echo "[$(date +%H:%M)] === Weekly update completado ===" >> "$LOG"
