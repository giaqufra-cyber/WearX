# Accessibilità di WearX

Obiettivo: **WCAG 2.2 livello AA** (lo stesso che chiede l'European Accessibility Act per i
servizi digitali venduti in UE dal 2025).

## Cosa si controlla da solo (a ogni modifica, CI)

`e2e/tests/accessibilita.spec.ts` e `e2e/tests/admin-accessibilita.spec.ts`: axe-core con le
regole WCAG 2.0/2.1/2.2 A e AA **più le buone pratiche** su:
- app (versione web): accoglienza, accesso, registrazione, password dimenticata, feed, esplora,
  profilo, crea, nuovo fit, notifiche, impostazioni, dispositivi, persone, cerca, pagina stile,
  dettaglio fit, profilo altrui pubblico e privato, moderazione, esportazione dati, cambio
  password, tipo di account, statistiche, foglio di segnalazione;
- pannello dello staff: accesso e tutte le sezioni.

Un solo problema e la CI diventa rossa.

## Cosa ha trovato e corretto l'audit (seduta 24)

| Problema | Dove | Correzione |
|---|---|---|
| Cursore del voto senza valore leggibile e senza tastiera | Feed, dettaglio | aria-valuenow/valuetext, frecce, PagSu/PagGiù, Home/Fine |
| `aria-selected` su pulsanti (non valido) | Filtri del feed, chip | Filtri come schede (`tablist`/`tab`); chip con `aria-pressed` sul web |
| Schede senza contenitore `tablist` | Persone, capsule del profilo | Aggiunto il contenitore |
| Foto senza testo alternativo | Griglia del profilo, notifiche, statistiche | Decorative (`alt=""`): il pulsante intorno ha già la descrizione |
| "Foto 1 di 1 del fit di Fit anonimo" | Carosello | "Foto del fit di @nick", "Foto 2 di 3, fit di @nick", "Foto del fit anonimo" |
| Due "Chiudi" e finestra dentro finestra | Fogli dal basso | Lo sfondo non è più un pulsante per i lettori; una sola finestra con nome |
| Due titoli di primo livello | Profilo privato, stati vuoti | Titoli secondari di livello 2 |
| `autocomplete` non valido sul web | Registrazione (nickname, data di nascita) | Nomi HTML (`username`, `bday-day`, …) |
| Nessuna zona principale | Tutta l'app web, accesso al pannello | `main` |
| Intestazioni di colonna vuote | Tabelle del pannello | "Azioni" per i lettori di schermo |
| Pagina di accesso senza titolo | Pannello | Titolo "WearX" |

Contrasto dei colori: nessun problema trovato da axe (testo secondario e terziario compresi).

## Cosa va provato a mano sul telefono (seduta 25, beta)

axe controlla la versione web: VoiceOver e TalkBack vanno provati su un telefono vero.
- VoiceOver (iOS) e TalkBack (Android): registrazione, voto, pubblicazione, segnalazione.
- Testo grande (Dimensioni testo al massimo): nessun testo tagliato nei pulsanti e nelle schede.
- Riduci movimento: animazioni del carosello e dei fogli.
- Aree toccabili di almeno 44x44 pt (già nel design: chip e icone hanno l'area allargata).
