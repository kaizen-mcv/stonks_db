# SLAs de frescura de datos

Lag esperado de cada tipo de dato según su cadencia de actualización.

## Por cadencia del pipeline

| Cadencia | Paso | Dato | Lag esperado | Fuente |
|----------|------|------|-------------|--------|
| **Diaria** (L-V 20:30+21:30) | daily_update | Precios equity/índices/ETFs/commodities | T+1 día | yfinance |
| | daily_update | Forex EUR/xxx | T+1 día | ECB |
| | daily_update | Crypto | T+1 día | CoinGecko |
| | daily_update | Yields/spreads US | T+1 día | FRED |
| | pipeline daily | Analistas (foto diaria) | T+1 día | yfinance |
| | pipeline daily | Opciones (snapshot) | T+1 día | yfinance |
| **Semanal** (Dom 8:00+10:00) | weekly_update | Fundamentales yfinance | T+7 días | yfinance |
| | pipeline weekly | Sectores/constituyentes | T+7 días | GitHub/Wikipedia |
| | pipeline weekly | SEC → bronze + PIT | T+1 a T+30 días | SEC EDGAR |
| | pipeline weekly | Empresa 360° (holders, insiders) | T+7 días | yfinance |
| **Mensual** (día 2, 6:00) | pipeline monthly | Factores (Value/Quality/Mom) | T+30 días | Calculado |
| | pipeline monthly | BIS tipos/crédito/REER | T+30-60 días | BIS |
| | pipeline monthly | OECD CPI mensual | T+30-60 días | OECD |
| | pipeline monthly | Eurostat HICP/paro/IP/PIB/retail | T+30-90 días | Eurostat |
| | pipeline monthly | Vintages ALFRED | T+30 días | FRED |
| **Semestral** (20 abr + 20 oct) | pipeline yearly | IMF WEO (proyecciones) | T-12 meses (proyecta) | IMF |
| | pipeline yearly | World Bank WDI (~1.500 indic.) | T+6-12 meses | World Bank |
| | pipeline yearly | Comercio bilateral (WITS) | T+6-18 meses | WITS |
| | pipeline yearly | Comercio por producto HS | T+6-12 meses | Comtrade |
| | pipeline yearly | Energía + CO2 | T+6 meses | OWID |
| | pipeline yearly | Agricultura (FAOSTAT) | T+6-12 meses | FAO |
| | pipeline yearly | Salud (WHO GHO) | T+6-12 meses | WHO |
| | pipeline yearly | Desigualdad (WID.world) | T+6-12 meses | WID |
| | pipeline yearly | Trabajo (ILOSTAT) | T+6-12 meses | ILO |

## Cómo comprobar la frescura

```sql
-- Resumen por dominio (generado por quality.py)
SELECT domain, entity_id, completeness_score,
       freshness_days, last_assessed
FROM meta.data_quality
WHERE entity_type = 'panel'
ORDER BY freshness_days DESC NULLS LAST;
```

```sql
-- Dato más reciente por fuente
SELECT ds.name, max(fr.ended_at) AS ultima_descarga,
       now() - max(fr.ended_at) AS hace
FROM meta.fetch_run fr
JOIN meta.data_source ds ON ds.id = fr.source_id
WHERE fr.status = 'success'
GROUP BY ds.name
ORDER BY ultima_descarga DESC;
```

## Notas

- **Macro anual** (WB, IMF, WHO, WID) se publica con 6-18 meses de lag
  respecto al año medido. El pipeline semestral (abril/octubre)
  coincide con las publicaciones del World Economic Outlook del IMF.
- **Macro mensual** (OECD, Eurostat, BIS) tiene lag de 1-3 meses.
- **Mercados** (equity, forex, crypto, commodities) están a T+1 día
  laborable.
- **SEC EDGAR** tiene lag variable: las empresas publican sus 10-K/10-Q
  entre T+1 y T+60 días tras el fin del período fiscal.
