"""Testi del server in inglese (seduta 34).

- `styles.name_en`, `styles.tagline_en`: nome e descrizione in inglese (vuoti = come in
  italiano). Qui si riempiono per gli stili del catalogo; quelli nuovi li scrive lo staff.
- `push_tokens.language`: la lingua dell'app su quel telefono, per scrivere i push nella stessa.
- `moderation_actions.statement_en`: la motivazione anche in inglese, scritta insieme a quella
  italiana (che resta il testo di riferimento).

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-30
"""

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

# slug -> (nome in inglese o None se uguale, descrizione in inglese)
STYLES: dict[str, tuple[str | None, str]] = {
    "old-money": (None, "Quiet luxury, cashmere, loafers"),
    "jappo": ("Tokyo Street", "Harajuku, layering, oversize"),
    "gala": ("Gala", "Black tie, long gowns, tuxedos"),
    "beach-party": (None, "Linen, swimwear, open shirts"),
    "elegant": (None, "Tailored, clean lines"),
    "country": (None, "Denim, boots, checks"),
    "halloween": (None, "Costumes, dark, cosplay"),
    "streetwear": (None, "Sneakers, hoodies, drops"),
    "y2k": (None, "Low-rise, metallics, the 2000s"),
    "gorpcore": (None, "Technical outdoor gear in the city"),
    "minimal": (None, "Neutral palette, few pieces"),
    "techwear": (None, "Black, straps, technical fabrics"),
    "casual": (None, "Everyday, no overthinking"),
    "business": (None, "Office, suits, smart casual"),
    "preppy": (None, "College, cardigans, loafers"),
    "vintage": (None, "Period pieces and second hand"),
    "workwear": (None, "Canvas, work boots, chore jackets"),
    "boho": (None, "Fringe, prints, maxi skirts"),
    "cottagecore": (None, "Florals, linen, countryside"),
    "coquette": (None, "Bows, powder pink, lace"),
    "dark-academia": (None, "Tweed, knitwear, libraries"),
    "k-fashion": (None, "Seoul street, pastels, idols"),
    "surf": (None, "Wetsuits, board shorts, salty hair"),
    "skate": (None, "Baggy fits, flat shoes, board under the arm"),
    "basket": ("Basketball", "Tank tops, jerseys, high-tops"),
    "calcio": ("Football", "Vintage shirts, scarves, blokecore"),
    "running": (None, "Technical, light, on pace"),
    "sci-snowboard": ("Ski & snowboard", "Technical jackets, après-ski"),
    "ciclismo": ("Cycling", "Race jerseys, gravel, helmets"),
    "tennis": (None, "Whites, polos, country club"),
    "golf": (None, "Polos, chinos, the green"),
    "gym": (None, "Athleisure, leggings, pump covers"),
    "arrampicata": ("Climbing", "Loose trousers, chalk, crags"),
    "gioielli": ("Jewellery", "Chains, rings, gold and silver"),
    "orologi": ("Watches", "On the wrist: vintage, sports, haute horlogerie"),
    "sneaker": ("Sneakers", "Drops, collections, on feet"),
    "borse": ("Bags", "Totes, baguettes, it-bags"),
    "occhiali": ("Eyewear", "Sunglasses and optical"),
    "cappelli": ("Hats", "Caps, beanies, panamas"),
    "make-up": (None, "Make-up, face looks, nail art"),
    "capelli": ("Hair", "Cuts, colours, hairstyles"),
    "emo": (None, "Fringes, black, band tees"),
    "goth": (None, "Black, lace, platforms"),
    "punk": (None, "Studs, tartan, safety pins"),
    "grunge": (None, "Flannel, ripped denim, the '90s"),
    "metal": (None, "Band tees, leather, combat boots"),
    "rockabilly": (None, "The '50s, quiffs, polka dots"),
    "hip-hop": (None, "Oversize, chains, caps"),
    "rave": (None, "Neon, mesh, techno"),
    "cosplay": (None, "Characters, costumes, conventions"),
    "matrimonio": ("Wedding", "As a guest: ceremony and reception"),
    "festival": (None, "Outdoor music, comfort and glitter"),
    "laurea": ("Graduation", "Graduation day"),
}


def _lit(value: str | None) -> str:
    if value is None:
        return "null"
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    op.execute(
        """
        alter table app.styles add column name_en text check (char_length(name_en) <= 40);
        alter table app.styles add column tagline_en text check (char_length(tagline_en) <= 90);
        alter table app.push_tokens add column language text not null default 'it'
          check (language in ('it', 'en'));
        alter table app.moderation_actions add column statement_en text;
        """
    )
    rows = ",\n".join(
        f"({_lit(slug)}, {_lit(name)}, {_lit(tagline)})" for slug, (name, tagline) in STYLES.items()
    )
    # SQL composto solo dai dati costanti di questo file (revisione Semgrep, seduta 22).
    op.execute(  # nosemgrep
        f"""
        update app.styles s set name_en = v.name_en, tagline_en = v.tagline_en
          from (values {rows}) as v(slug, name_en, tagline_en)
         where s.slug = v.slug;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        alter table app.moderation_actions drop column statement_en;
        alter table app.push_tokens drop column language;
        alter table app.styles drop column tagline_en;
        alter table app.styles drop column name_en;
        """
    )
