"""Genera docs/CERTIFICACION.md desde meta.table_certification.

Certifica primero y escribe despues, para que el documento nunca sea
una foto antigua. Regenerable: `python scripts/gen_certificacion.py`.
"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import text

import stonks.models  # noqa: F401  (registra los modelos)
from stonks.certificacion import (
    COHERENTE,
    CONTRASTADA,
    NO_VERIFICABLE,
    SIN_CERTIFICAR,
    certificar,
)
from stonks.db import engine

SALIDA = Path(__file__).resolve().parent.parent / "docs" / "CERTIFICACION.md"

_TITULOS = {
    CONTRASTADA: "Contrastadas contra una cifra publicada fuera",
    COHERENTE: "Coherentes, sin cifra externa con la que comparar",
    NO_VERIFICABLE: "No verificables",
    SIN_CERTIFICAR: "Sin certificar",
}

_EXPLICACIONES = {
    CONTRASTADA: (
        "Hay al menos un valor en `tests/referencias.yml` que compara "
        "una fila de la tabla contra una cifra publicada por la fuente "
        "original. Es la única categoría que responde \"sí\" a *¿son "
        "ciertos estos datos?*; el resto responde a *¿son posibles?*."
    ),
    COHERENTE: (
        "No existe una cifra externa razonable con la que comparar "
        "—son catálogos, agregados propios o fotos que nadie archiva—, "
        "pero sí comprobaciones estructurales que la tabla pasa."
    ),
    NO_VERIFICABLE: (
        "Se ha mirado y no hay forma de comprobarlas. Cada una lleva su "
        "motivo escrito; un test falla si alguien marca una tabla así "
        "sin explicar por qué."
    ),
    SIN_CERTIFICAR: (
        "Nadie ha declarado cómo se comprueban. **Este apartado debe "
        "estar vacío**: hay un test que falla si no lo está."
    ),
}


def main() -> None:
    """Certificar y escribir el documento."""
    certificar(por="scripts/gen_certificacion.py")

    with engine.begin() as conn:
        filas = conn.execute(
            text(
                "SELECT estado, schema_name, table_name, filas, "
                "       referencias, metodo, motivo "
                "FROM meta.table_certification "
                "ORDER BY schema_name, table_name"
            )
        ).fetchall()

    por_estado: dict[str, list] = {}
    for f in filas:
        por_estado.setdefault(f[0], []).append(f)

    total = len(filas)
    lineas = [
        "# Certificación de stonks_db",
        "",
        f"_Generado el {datetime.now():%Y-%m-%d} por "
        "`scripts/gen_certificacion.py`. No editar a mano: las "
        "declaraciones van en `config/certificacion.yml` y las "
        "referencias externas en `tests/referencias.yml`._",
        "",
        "## Qué certifica esto, y qué no",
        "",
        "Con datos de terceros no se puede garantizar que cada cifra "
        "sea cierta: si el World Bank publica mal un PIB, esta base lo "
        "reproduce fielmente. Prometer *\"todos los datos son "
        "correctos\"* sería mentir.",
        "",
        "Lo que sí se garantiza, y es lo que hay aquí, es que **de "
        "cada una de las tablas consta cómo se ha verificado, o consta "
        "explícitamente que no se puede verificar y por qué**. Eso es "
        "auditable; lo otro no.",
        "",
        "## Resumen",
        "",
        "| Estado | Tablas | % |",
        "|---|---:|---:|",
    ]

    for estado in (CONTRASTADA, COHERENTE, NO_VERIFICABLE, SIN_CERTIFICAR):
        n = len(por_estado.get(estado, []))
        lineas.append(
            f"| {estado} | {n} | {100.0 * n / total:.1f} % |"
        )
    lineas += ["", f"**{total} tablas** en total.", ""]

    for estado in (CONTRASTADA, COHERENTE, NO_VERIFICABLE, SIN_CERTIFICAR):
        grupo = por_estado.get(estado, [])
        lineas += [f"## {_TITULOS[estado]}", "", _EXPLICACIONES[estado], ""]
        if not grupo:
            lineas += ["_Ninguna._", ""]
            continue
        lineas += ["| Tabla | Filas | Cómo se comprueba |", "|---|---:|---|"]
        for _e, esq, tab, nfilas, _refs, metodo, motivo in grupo:
            texto = (metodo or motivo or "").replace("\n", " ").strip()
            lineas.append(
                f"| `{esq}.{tab}` | {nfilas or 0:,} | {texto} |"
            )
        lineas.append("")

    lineas += [
        "## Cómo se mantiene",
        "",
        "1. `stonks certify` recorre las tablas y actualiza "
        "`meta.table_certification`.",
        "2. Una tabla queda **contrastada** sola, sin declarar nada, en "
        "cuanto alguna consulta de `tests/referencias.yml` la nombra.",
        "3. Lo que no se pueda contrastar se declara a mano en "
        "`config/certificacion.yml`, con su método o su motivo.",
        "4. `tests/test_referencias.py` falla si alguna tabla se queda "
        "sin declarar, así que **no se puede añadir una tabla nueva "
        "sin decir cómo se comprueba**.",
        "",
    ]

    SALIDA.write_text("\n".join(lineas), encoding="utf-8")
    print(f"Escrito {SALIDA} ({total} tablas)")


if __name__ == "__main__":
    main()
