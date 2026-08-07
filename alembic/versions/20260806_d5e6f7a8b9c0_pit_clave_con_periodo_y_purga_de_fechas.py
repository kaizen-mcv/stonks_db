"""PIT: clave con periodo y purga de fechas imposibles

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-08-06

Dos cambios en `gold.fact_fundamentals_pit`.

**1. La clave unica no incluia `period_end_date`.** Dos periodos
distintos presentados en el mismo informe y con el mismo trimestre
fiscal podian pisarse. Medido sobre 1.174.081 claves: hoy **no
colisiona ninguna**, porque `_classify_period` deriva el trimestre de
las fechas reales del hecho y eso ya los distingue. Aun asi la clave
sin el periodo no lo garantiza, y anadirlo es barato.

Conviene dejar claro lo que NO es un problema, porque a primera vista
lo parece: el 13 % de las filas tiene `fiscal_year` desalineado del ano
de `period_end_date`. Es convencion contable, no corrupcion. El
ejercicio fiscal 2025 de Apple empieza en octubre de 2024, asi que su
primer trimestre cierra en diciembre de 2024: desfase de -1 y
perfectamente correcto.

**2. Fechas imposibles.** 272 filas con `period_end_date` en 2105, en
6016 o en fechas equivalentes. Son erratas de las propias
presentaciones ante la SEC, no de la ingesta. Se borran porque
envenenan cualquier consulta point-in-time por rango de fechas.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CLAVE_VIEJA = (
    "fact_fundamentals_pit_company_id_statement_type_fiscal_year_f_key"
)
CLAVE_NUEVA = "uq_pit_clave_completa"


def upgrade() -> None:
    """Purgar fechas imposibles y ampliar la clave unica."""
    op.execute(
        """
        DELETE FROM gold.fact_fundamentals_pit
        WHERE period_end_date < DATE '1970-01-01'
           OR period_end_date > CURRENT_DATE + 400
           OR filed_date < DATE '1993-01-01'
           OR filed_date > CURRENT_DATE
        """
    )

    # El nombre autogenerado se trunca, asi que se localiza por sus
    # columnas en vez de darlo por supuesto.
    op.execute(
        """
        DO $$
        DECLARE nombre text;
        BEGIN
            SELECT conname INTO nombre
            FROM pg_constraint
            WHERE conrelid = 'gold.fact_fundamentals_pit'::regclass
              AND contype = 'u'
            LIMIT 1;
            IF nombre IS NOT NULL THEN
                EXECUTE format(
                    'ALTER TABLE gold.fact_fundamentals_pit '
                    'DROP CONSTRAINT %I', nombre);
            END IF;
        END $$
        """
    )
    op.execute(
        f"ALTER TABLE gold.fact_fundamentals_pit "
        f"ADD CONSTRAINT {CLAVE_NUEVA} UNIQUE "
        "(company_id, statement_type, fiscal_year, fiscal_quarter, "
        " filed_date, metric, period_end_date)"
    )


def downgrade() -> None:
    """Volver a la clave sin el periodo.

    Las filas con fechas imposibles no se recuperan: habria que volver
    a procesar los snapshots de bronze.
    """
    op.execute(
        f"ALTER TABLE gold.fact_fundamentals_pit "
        f"DROP CONSTRAINT IF EXISTS {CLAVE_NUEVA}"
    )
    op.execute(
        "ALTER TABLE gold.fact_fundamentals_pit "
        f"ADD CONSTRAINT {CLAVE_VIEJA} UNIQUE "
        "(company_id, statement_type, fiscal_year, fiscal_quarter, "
        " filed_date, metric)"
    )
