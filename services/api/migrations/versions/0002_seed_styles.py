"""Stili iniziali, dal prototipo. Da qui in poi gli stili si gestiscono dall'admin.

Beach Party è riservato ai 18+ (proposta D3 della specifica, sez. 14.1).
Halloween è stagionale (1 ottobre - 1 novembre 2026).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

STYLES = [
    # slug, nome, tagline, tono, fascia minima, attivo dal, attivo fino al, ordine
    (
        "old-money",
        "Old Money",
        "Quiet luxury, cachemire, mocassini",
        "#2F3A2B",
        "16_17",
        None,
        None,
        10,
    ),
    ("jappo", "Jappo", "Tokyo street, layering, oversize", "#1F2946", "16_17", None, None, 20),
    ("gala", "Galà", "Black tie, abiti lunghi, smoking", "#3D1018", "16_17", None, None, 30),
    (
        "beach-party",
        "Beach Party",
        "Lino, costumi, camicie aperte",
        "#0E4A57",
        "18_plus",
        None,
        None,
        40,
    ),
    ("elegant", "Elegant", "Sartoriale, linee pulite", "#2A2A2F", "16_17", None, None, 50),
    ("country", "Country", "Denim, stivali, quadri", "#5A3A21", "16_17", None, None, 60),
    (
        "halloween",
        "Halloween",
        "Costumi, dark, cosplay",
        "#3E1F06",
        "16_17",
        "2026-10-01",
        "2026-11-01",
        5,
    ),
    ("streetwear", "Streetwear", "Sneakers, hoodie, drop", "#33302B", "16_17", None, None, 70),
    ("y2k", "Y2K", "Vita bassa, metallici, anni 2000", "#43285A", "16_17", None, None, 80),
    ("gorpcore", "Gorpcore", "Outdoor tecnico in città", "#36452A", "16_17", None, None, 90),
    ("minimal", "Minimal", "Palette neutra, pochi capi", "#4E4A45", "16_17", None, None, 100),
    ("techwear", "Techwear", "Nero, cinghie, tessuti tecnici", "#181B20", "16_17", None, None, 110),
]


def _lit(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def upgrade() -> None:
    rows = ",\n".join("(" + ", ".join(_lit(v) for v in row) + ")" for row in STYLES)
    # SQL composto solo dai dati costanti di questo file (revisione Semgrep, seduta 22).
    op.execute(  # nosemgrep
        f"""
        insert into app.styles
          (slug, name, tagline, tone, min_age_band, active_from, active_until, sort_order)
        values
        {rows};
        """
    )


def downgrade() -> None:
    slugs = ", ".join(_lit(s[0]) for s in STYLES)
    # SQL composto solo dai dati costanti di questo file (revisione Semgrep, seduta 22).
    op.execute(f"delete from app.styles where slug in ({slugs});")  # nosemgrep
