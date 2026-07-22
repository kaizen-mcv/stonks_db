"""Genera docs/DATA_DICTIONARY.md introspeccionando la BD real.

Recorre PostgreSQL (pg_catalog) para listar, por esquema, cada tabla /
vista / materializada con sus columnas, tipos, claves (PK/FK) y nº de
filas. Las descripciones de tabla salen de los docstrings de los modelos
SQLAlchemy. Regenerable: `python scripts/gen_data_dictionary.py`.
"""

from pathlib import Path

from sqlalchemy import text

import stonks.models  # noqa: F401  (registra los modelos)
from stonks.db import Base, engine

# Grupos de esquemas (orden y título del documento)
GROUPS = [
    ("Referencia y metadatos", ["ref", "meta"]),
    (
        "Renta variable y mercados financieros",
        ["equity", "fi", "commodity", "forex", "crypto", "fund", "alt"],
    ),
    ("Economía mundial", ["macro", "trade", "energy", "agri", "country"]),
    ("Derivados", ["deriv"]),
    ("Medallion — aterrizaje y analítica", ["bronze", "gold"]),
]

SCHEMA_DESC = {
    "ref": "Datos de referencia: países, divisas, bolsas, sectores GICS.",
    "meta": "Metadatos y auditoría: fuentes, ejecuciones, calidad.",
    "macro": "Economía mundial como series país × indicador × fecha.",
    "equity": "Renta variable: empresas, precios, fundamentales y 360°.",
    "fi": "Renta fija: bonos, ratings, curvas de tipos.",
    "commodity": "Materias primas y sus precios.",
    "forex": "Divisas y tipos de cambio.",
    "crypto": "Criptomonedas.",
    "fund": "ETFs y fondos.",
    "alt": "Datos alternativos: sentimiento, vivienda.",
    "trade": "Comercio internacional bilateral (país × socio).",
    "energy": "Balance energético por país, fuente y flujo.",
    "agri": "Producción agrícola por país, cultivo/ganado y elemento.",
    "country": "Perfiles de país: demografía, impuestos.",
    "deriv": "Derivados: snapshots de cadenas de opciones.",
    "bronze": "Aterrizaje crudo (JSONB) de las fuentes nuevas.",
    "gold": "Capa analítica point-in-time: hechos, dimensiones y marts.",
}

# Descripción curada de vistas/materializadas de gold (no son modelos ORM)
VIEW_DESC = {
    "mart_country_year": "Panel ancho país × año: macro + energía + "
    "comercio + emisiones (tabla analítica principal).",
    "mart_trade_matrix": "Matriz de comercio bilateral reporter × "
    "partner × año (exportaciones e importaciones).",
    "mart_benchmark_returns": "Retorno diario del pool S&P 500 "
    "equiponderado (survivorship-free) vs SPY.",
    "mart_pool_membership": "Universo S&P 500 point-in-time expandido a "
    "días de cotización.",
    "dim_indicator": "Catálogo autodocumentado de indicadores macro "
    "(código, fuente, cobertura, rango).",
}

KIND = {"r": "tabla", "m": "materializada", "v": "vista", "p": "tabla"}


def _table_docs() -> dict[tuple[str, str], str]:
    """(esquema, tabla) → docstring del modelo SQLAlchemy."""
    out: dict[tuple[str, str], str] = {}
    for mapper in Base.registry.mappers:
        t = mapper.local_table
        if t is None or t.schema is None:
            continue
        doc = (mapper.class_.__doc__ or "").strip().split("\n")[0]
        out[(t.schema, t.name)] = doc
    return out


def _relations(conn, schema: str):
    """Relaciones (tabla/vista/matview) de un esquema, con nº de filas."""
    sql = text(
        "SELECT c.relname, c.relkind, "
        "  CASE WHEN c.reltuples < 0 THEN 0 ELSE c.reltuples::bigint END "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = :s AND c.relkind IN ('r','m','v','p') "
        "ORDER BY c.relname"
    )
    return list(conn.execute(sql, {"s": schema}))


def _columns(conn, schema: str, table: str):
    """Columnas (nombre, tipo, nullable) de una relación."""
    sql = text(
        "SELECT a.attname, format_type(a.atttypid, a.atttypmod), "
        "  NOT a.attnotnull "
        "FROM pg_attribute a "
        "JOIN pg_class c ON c.oid = a.attrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = :s AND c.relname = :t "
        "  AND a.attnum > 0 AND NOT a.attisdropped "
        "ORDER BY a.attnum"
    )
    return list(conn.execute(sql, {"s": schema, "t": table}))


def _keys(conn, schema: str, table: str):
    """Devuelve (set de columnas PK, dict col→destino FK)."""
    p = {"s": schema, "t": table}
    pk = {
        r[0]
        for r in conn.execute(
            text(
                "SELECT a.attname FROM pg_index i "
                "JOIN pg_class c ON c.oid = i.indrelid "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "JOIN pg_attribute a ON a.attrelid = i.indrelid "
                "  AND a.attnum = ANY(i.indkey) "
                "WHERE n.nspname = :s AND c.relname = :t "
                "  AND i.indisprimary"
            ),
            p,
        )
    }
    fk = {}
    for col, fs, ft, fc in conn.execute(
        text(
            "SELECT att.attname, ns2.nspname, cl2.relname, att2.attname "
            "FROM pg_constraint con "
            "JOIN pg_class cl ON cl.oid = con.conrelid "
            "JOIN pg_namespace ns ON ns.oid = cl.relnamespace "
            "JOIN pg_attribute att ON att.attrelid = con.conrelid "
            "  AND att.attnum = ANY(con.conkey) "
            "JOIN pg_class cl2 ON cl2.oid = con.confrelid "
            "JOIN pg_namespace ns2 ON ns2.oid = cl2.relnamespace "
            "JOIN pg_attribute att2 ON att2.attrelid = con.confrelid "
            "  AND att2.attnum = ANY(con.confkey) "
            "WHERE ns.nspname = :s AND cl.relname = :t "
            "  AND con.contype = 'f'"
        ),
        p,
    ):
        fk[col] = f"{fs}.{ft}.{fc}"
    return pk, fk


def generate() -> str:
    docs = _table_docs()
    out = [
        "# Diccionario de datos — stonks_db",
        "",
        "> Generado automáticamente desde el esquema real "
        "(`python scripts/gen_data_dictionary.py`).",
        "> No editar a mano. Para el diseño ver "
        "[ARCHITECTURE.md](ARCHITECTURE.md) y "
        "[SCHEMA_RELATIONS.md](SCHEMA_RELATIONS.md).",
        "",
    ]
    with engine.connect() as conn:
        for grupo, schemas in GROUPS:
            out.append(f"## {grupo}\n")
            for schema in schemas:
                rels = _relations(conn, schema)
                if not rels:
                    continue
                out.append(f"### Esquema `{schema}`")
                out.append(f"_{SCHEMA_DESC.get(schema, '')}_\n")
                for name, kind, nrows in rels:
                    desc = docs.get((schema, name)) or VIEW_DESC.get(name, "")
                    etiqueta = KIND.get(kind, kind)
                    out.append(
                        f"#### `{schema}.{name}` "
                        f"· {etiqueta} · ~{nrows:,} filas"
                    )
                    if desc:
                        out.append(f"{desc}\n")
                    pk, fk = _keys(conn, schema, name)
                    out.append("| Columna | Tipo | Nulo | Clave |")
                    out.append("|---|---|---|---|")
                    for col, tipo, nullable in _columns(conn, schema, name):
                        clave = ""
                        if col in pk:
                            clave = "PK"
                        elif col in fk:
                            clave = f"FK → {fk[col]}"
                        nulo = "sí" if nullable else "no"
                        out.append(f"| `{col}` | {tipo} | {nulo} | {clave} |")
                    out.append("")
    return "\n".join(out)


if __name__ == "__main__":
    destino = Path(__file__).resolve().parent.parent / "docs"
    destino.mkdir(exist_ok=True)
    (destino / "DATA_DICTIONARY.md").write_text(generate(), encoding="utf-8")
    print("Escrito docs/DATA_DICTIONARY.md")
