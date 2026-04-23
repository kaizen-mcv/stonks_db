# Contribuir a stonks_db

Gracias por tu interés en contribuir. Este documento explica cómo
participar en el proyecto.

## Código de conducta

Este proyecto sigue el [Contributor Covenant](CODE_OF_CONDUCT.md).
Al participar, te comprometes a respetar sus principios.

## Cómo empezar

### Requisitos

- Python 3.11+
- PostgreSQL 14+
- Git

### Configuración del entorno de desarrollo

```bash
# Clonar el repo
git clone git@github.com:kaizen-mcv/stonks_db.git
cd stonks_db

# Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Instalar en modo desarrollo (incluye herramientas dev)
pip install -e ".[dev]"

# Crear base de datos
createdb stonks_db

# Copiar plantilla de configuración
cp .env.example .env
# Editar .env con tus credenciales

# Inicializar tablas y datos de referencia
stonks init
```

### Ejecutar linters

```bash
ruff check .
ruff format --check .
```

Para auto-formatear:

```bash
ruff format .
```

## Flujo de trabajo

### 1. Crear una issue primero

Antes de empezar a codear algo grande, abre una issue para
discutirlo. Para bugs pequeños o typos puedes ir directo al PR.

### 2. Crear una rama

Usa nombres descriptivos:

- `feat/nombre-funcionalidad`
- `fix/descripcion-bug`
- `docs/que-se-documenta`
- `refactor/area-refactorizada`

```bash
git checkout -b feat/nuevo-fetcher-wipo
```

### 3. Hacer commits

Usa el formato [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` nueva funcionalidad
- `fix:` corrección de bug
- `docs:` cambios en documentación
- `refactor:` refactorización sin cambio funcional
- `chore:` tareas de mantenimiento
- `ci:` cambios en CI/CD
- `test:` añadir o modificar tests

Ejemplo:

```
feat(fi): añadir fetcher de bonos corporativos

Nuevo BondCorporateFetcher que descarga de la SEC EDGAR.
Incluye rate limiting y estado incremental.
```

### 4. Abrir Pull Request

- Describe claramente qué cambia y por qué
- Referencia la issue relacionada (`Closes #123`)
- Asegúrate de que CI pase
- Mantén los PRs pequeños y enfocados

## Convenciones de código

- **Estilo**: Seguir PEP 8 (ruff se encarga)
- **Línea máxima**: 79 caracteres
- **Comentarios**: En español
- **Variables**: `snake_case`
- **Clases**: `PascalCase`
- **Constantes**: `UPPER_SNAKE_CASE`
- **Logging**: Usar `logging`, nunca `print()` para debug
- **Simplicidad**: Preferir código simple a sobreingeniería

## Añadir un nuevo fetcher

Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para una guía
paso a paso.

## Estructura del proyecto

```
stonks_db/
├── src/stonks/
│   ├── cli.py          # CLI Typer
│   ├── config.py       # Configuración Pydantic
│   ├── db.py           # SQLAlchemy engine
│   ├── logger.py       # Logging
│   ├── fetchers/       # Descargadores por fuente
│   └── models/         # Modelos SQLAlchemy
├── config/             # YAML de configuración
├── scripts/            # Scripts de utilidad
├── docs/               # Documentación
└── tests/              # Tests (futuro)
```

## Preguntas

Si tienes dudas, abre una issue con la etiqueta `question`.
