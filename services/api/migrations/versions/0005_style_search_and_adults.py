"""Ricerca degli stili senza accenti e passaggio automatico ai 18 anni.

- app.fold(): minuscolo e senza accenti (translate, nessuna estensione in più): "Galà"
  si trova scrivendo "gala". L'indice trigram usa la stessa funzione.
- app.promote_adults(): chi ha compiuto 18 anni passa alla fascia 18+ (lo chiama l'API
  quando legge il profilo e, più avanti, un job notturno).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-04
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# Solo minuscole: la funzione applica lower() prima di translate().
FROM = "àáâãäåāèéêëēìíîïīòóôõöøōùúûüūñçß"
TO = "aaaaaaaeeeeeiiiiiooooooouuuuuncs"
assert len(FROM) == len(TO)


def upgrade() -> None:
    # SQL composto solo dai dati costanti di questo file (revisione Semgrep, seduta 22).
    op.execute(  # nosemgrep
        f"""
        create function app.fold(t text) returns text
          language sql immutable parallel safe strict
          as $$ select translate(lower(t), '{FROM}', '{TO}') $$;

        drop index app.styles_search_trgm;
        create index styles_search_trgm on app.styles
          using gin (app.fold(name || ' ' || tagline) gin_trgm_ops);

        create function app.promote_adults(only_user uuid default null) returns integer
          language sql volatile
          as $$
            with up as (
              update app.profiles
                 set age_band = '18_plus', adult_on = null
               where age_band = '16_17' and adult_on <= current_date
                 and (only_user is null or id = only_user)
              returning 1)
            select count(*)::integer from up
          $$;

        grant execute on function app.fold(text) to wearx_api;
        grant execute on function app.promote_adults(uuid) to wearx_api;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        drop function app.promote_adults(uuid);
        drop index app.styles_search_trgm;
        create index styles_search_trgm on app.styles
          using gin ((name || ' ' || tagline) gin_trgm_ops);
        drop function app.fold(text);
        """
    )
