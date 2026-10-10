"""Catalogo stili ampio, con categorie (seduta 29).

Agli stili si aggiunge una categoria (stili, sport, accessori, beauty, sottoculture, occasioni)
per poterli sfogliare a gruppi. Gli stili nuovi partono senza iscritti: in Esplora e nella scelta
dello stile quando si pubblica l'ordine è per numero di iscritti, poi per `sort_order`.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-11
"""

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None

CATEGORIES = ("stili", "sport", "accessori", "beauty", "sottoculture", "occasioni")

# Stili già presenti -> categoria (gli altri restano "stili").
EXISTING = {"gala": "occasioni", "beach-party": "occasioni", "halloween": "occasioni"}

NEW = [
    # slug, nome, descrizione, tono, categoria, ordine
    ("casual", "Casual", "Tutti i giorni, senza pensarci", "#3B3F45", "stili", 120),
    ("business", "Business", "Ufficio, completo, smart casual", "#22303D", "stili", 130),
    ("preppy", "Preppy", "College, cardigan, mocassini", "#2B3A55", "stili", 140),
    ("vintage", "Vintage", "Pezzi d'epoca e second hand", "#5B4630", "stili", 150),
    ("workwear", "Workwear", "Tela, scarponi, giacche da lavoro", "#4F4223", "stili", 160),
    ("boho", "Boho", "Frange, stampe, gonne lunghe", "#6A4A2E", "stili", 170),
    ("cottagecore", "Cottagecore", "Fiori, lino, campagna", "#4B5A3A", "stili", 180),
    ("coquette", "Coquette", "Fiocchi, rosa cipria, pizzo", "#6B3A4A", "stili", 190),
    ("dark-academia", "Dark Academia", "Tweed, maglioni, biblioteche", "#3A2E24", "stili", 200),
    ("k-fashion", "K-fashion", "Seoul street, pastello, idol", "#4A3C5C", "stili", 210),
    ("surf", "Surf", "Mute, board shorts, sale nei capelli", "#0F4C5C", "sport", 300),
    ("skate", "Skate", "Baggy, scarpe piatte, tavola sotto il braccio", "#3C3A36", "sport", 310),
    ("basket", "Basket", "Canotte, jersey, sneaker alte", "#6A2C14", "sport", 320),
    ("calcio", "Calcio", "Maglie vintage, sciarpe, blokecore", "#1E4A2C", "sport", 330),
    ("running", "Running", "Tecnico, leggero, a ritmo", "#2C3E50", "sport", 340),
    ("sci-snowboard", "Sci e snowboard", "Giacche tecniche, après-ski", "#1F3A5F", "sport", 350),
    ("ciclismo", "Ciclismo", "Maglie da gara, gravel, caschi", "#2D2F4A", "sport", 360),
    ("tennis", "Tennis", "Bianco, polo, country club", "#2F4A3A", "sport", 370),
    ("golf", "Golf", "Polo, chino, green", "#33502F", "sport", 380),
    ("gym", "Gym", "Athleisure, leggings, pump cover", "#2A2A33", "sport", 390),
    ("arrampicata", "Arrampicata", "Pantaloni larghi, magnesite, falesia", "#4A3B2A", "sport", 400),
    ("gioielli", "Gioielli", "Catene, anelli, oro e argento", "#5C4A1E", "accessori", 500),
    ("orologi", "Orologi", "Al polso: vintage, sportivi, d'autore", "#2E3338", "accessori", 510),
    ("sneaker", "Sneaker", "Drop, collezioni, on feet", "#3A2F3F", "accessori", 520),
    ("borse", "Borse", "Tote, baguette, it-bag", "#4F2E2A", "accessori", 530),
    ("occhiali", "Occhiali", "Da sole e da vista", "#26323A", "accessori", 540),
    ("cappelli", "Cappelli", "Cappellini, berretti, panama", "#3E3A2A", "accessori", 550),
    ("make-up", "Make-up", "Trucco, look viso, nail art", "#5A2A3C", "beauty", 600),
    ("capelli", "Capelli", "Tagli, colori, acconciature", "#3F2A22", "beauty", 610),
    ("emo", "Emo", "Frangia, nero, band tee", "#1C1C24", "sottoculture", 700),
    ("goth", "Goth", "Nero, pizzo, platform", "#1E1420", "sottoculture", 710),
    ("punk", "Punk", "Borchie, tartan, spille", "#4A1418", "sottoculture", 720),
    ("grunge", "Grunge", "Flanella, denim strappato, anni '90", "#3A3426", "sottoculture", 730),
    ("metal", "Metal", "Band tee, pelle, anfibi", "#202022", "sottoculture", 740),
    ("rockabilly", "Rockabilly", "Anni '50, ciuffo, pois", "#5A1E24", "sottoculture", 750),
    ("hip-hop", "Hip hop", "Oversize, catene, cappellini", "#2E2A22", "sottoculture", 760),
    ("rave", "Rave", "Neon, mesh, techno", "#2A1F4A", "sottoculture", 770),
    ("cosplay", "Cosplay", "Personaggi, costumi, convention", "#3D2A55", "sottoculture", 780),
    (
        "matrimonio",
        "Matrimonio",
        "Da invitato: cerimonia e ricevimento",
        "#4A3A3F",
        "occasioni",
        800,
    ),
    ("festival", "Festival", "Musica all'aperto, comodità e glitter", "#4A2A55", "occasioni", 810),
    ("laurea", "Laurea", "Il giorno della proclamazione", "#2A3A4A", "occasioni", 820),
]


def _lit(value: object) -> str:
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def upgrade() -> None:
    allowed = ", ".join(_lit(c) for c in CATEGORIES)
    # SQL composto solo dai dati costanti di questo file (revisione Semgrep, seduta 22).
    op.execute(  # nosemgrep
        f"""
        alter table app.styles add column category text not null default 'stili'
          check (category in ({allowed}));
        create index styles_category on app.styles (category);
        """
    )
    for slug, category in EXISTING.items():
        op.execute(  # nosemgrep
            f"update app.styles set category = {_lit(category)} where slug = {_lit(slug)};"
        )
    rows = ",\n".join("(" + ", ".join(_lit(v) for v in row) + ")" for row in NEW)
    op.execute(  # nosemgrep
        f"""
        insert into app.styles (slug, name, tagline, tone, category, sort_order)
        values
        {rows}
        on conflict (slug) do nothing;
        """
    )


def downgrade() -> None:
    slugs = ", ".join(_lit(row[0]) for row in NEW)
    op.execute(  # nosemgrep
        f"""
        delete from app.style_memberships
         where style_id in (select id from app.styles where slug in ({slugs}));
        delete from app.styles s where s.slug in ({slugs})
           and not exists (select 1 from app.posts p where p.style_id = s.id);
        alter table app.styles drop column category;
        """
    )
