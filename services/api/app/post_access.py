"""Chi può vedere un post e chi ne vede l'autore. Frammenti SQL riusati da post e feed.

Parametri attesi: :viewer (uuid) e :adult (bool) del profilo che guarda.
- Il proprio post si vede sempre (tranne se eliminato), qualunque sia lo stato.
- Un post altrui si vede se: attivo (o fuori stile), autore attivo, stile permesso alla
  fascia d'età di chi guarda (i 16-17 non vedono i post degli stili 18+), pubblicato da un
  adulto oppure chi guarda ha 16-17 anni (i fit dei 16-17 restano tra 16-17), nessun blocco
  in nessuna direzione.
- L'autore compare se: account Business, oppure sei tu, oppure lo segui (richiesta accettata).
  Altrimenti il post è anonimo (sez. 6.6: i profili privati restano anonimi nei feed).
"""

POST_VISIBLE_SQL = """
(
  (p.author_id = :viewer and p.status <> 'deleted')
  or (
    -- style_rejected: fuori dalla pagina dello stile ma ancora nel portfolio dell'autore.
    p.status in ('active', 'style_rejected')
    and a.status = 'active'
    and (cast(:adult as boolean) or s.min_age_band <> '18_plus')
    -- Fit pubblicati da un 16-17enne: solo per altri 16-17 (sez. 14.1).
    and (not p.minor_author or not cast(:adult as boolean))
    and not exists (
      select 1 from app.blocks b
       where (b.blocker_id = :viewer and b.blocked_id = p.author_id)
          or (b.blocker_id = p.author_id and b.blocked_id = :viewer)
    )
  )
)
"""

AUTHOR_SHOWN_SQL = """
(
  a.account_type = 'business'
  or p.author_id = :viewer
  or exists (
    select 1 from app.follows f
     where f.follower_id = :viewer and f.followee_id = p.author_id and f.status = 'accepted'
  )
)
"""
