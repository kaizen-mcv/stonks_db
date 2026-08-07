"""Columnas de trazabilidad compartidas.

De 68 tablas de datos, 25 declaraban `source_id` y solo 5
`fetch_run_id`. Cuando un dato sale raro, la primera pregunta es quien
lo escribio y en que ejecucion, y sin estas dos columnas no habia
forma de responderla.

Se declaran como mixin y no tabla a tabla para que anadirlas a un
modelo nuevo sea escribir una palabra, no copiar seis lineas.

Ninguna de las dos lleva clave foranea a proposito. `meta.fetch_run`
se puede podar sin que las filas de datos dejen de ser validas, y una
FK sobre `source_id` obligaria a indexar 39 columnas de baja
cardinalidad —el proyecto exige indice en toda FK— a cambio de una
integridad que ningun fetcher pone en riesgo.
"""

from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column


class Linaje:
    """Origen y ejecucion que escribieron la fila."""

    source_id: Mapped[int | None] = mapped_column(Integer)
    fetch_run_id: Mapped[int | None] = mapped_column(Integer)


class LinajeEjecucion:
    """Solo la ejecucion, para las tablas que ya declaran el origen."""

    fetch_run_id: Mapped[int | None] = mapped_column(Integer)
