# Política de Seguridad

## Versiones soportadas

Actualmente solo la versión más reciente recibe actualizaciones de
seguridad:

| Versión | Soportada |
|---------|-----------|
| 0.2.x   | ✅        |
| 0.1.x   | ❌        |

## Reportar una vulnerabilidad

Si descubres una vulnerabilidad de seguridad en `stonks_db`, por favor
**no abras una issue pública**. En su lugar:

1. Usa la funcionalidad
   [Security Advisories de GitHub](https://github.com/kaizen-mcv/stonks_db/security/advisories/new)
   para reportarla de forma privada.
2. Describe:
   - El tipo de vulnerabilidad
   - Cómo reproducirla
   - Impacto potencial
   - Sugerencia de mitigación (si la tienes)

## Tiempo de respuesta

Intentaremos responder en un plazo de **7 días naturales**. Si la
vulnerabilidad es crítica, se publicará un parche lo antes posible.

## Alcance

Este proyecto:

- Es una base de datos local (no expone endpoints públicos)
- No maneja datos personales de usuarios finales
- Depende de APIs externas (FRED, yfinance, ECB, etc.) cuyas
  credenciales son responsabilidad del usuario

Las principales superficies de ataque a considerar:

- Inyección SQL vía inputs del CLI
- Deserialización insegura de datos externos
- Exposición accidental de API keys en logs o commits

## Buenas prácticas recomendadas

- **Nunca** commitear `.env` con claves reales
- Usar `.env.example` como plantilla
- Rotar API keys si fueron expuestas por error
- Mantener PostgreSQL actualizado y con acceso restringido
