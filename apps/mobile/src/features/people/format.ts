/** Testi della ricerca persone (seduta 31): riga sotto il nickname e parte evidenziata. */
import type { PersonCard } from "@wearx/api-types";

/** Come il server: "@Giulia.R " -> "giulia.r" (nickname minuscoli, senza spazi né simboli). */
export function normalizeQuery(raw: string): string {
  return raw
    .trim()
    .replace(/^@+/, "")
    .toLowerCase()
    .replace(/[^a-z0-9._]/g, "")
    .slice(0, 30);
}

function followersLabel(count: number): string {
  // Punto delle migliaia a mano: non tutti i motori JS del telefono hanno le regole italiane.
  return count === 1 ? "1 follower" : `${String(count).replace(/\B(?=(\d{3})+(?!\d))/g, ".")} follower`;
}

function mutualLine(card: Pick<PersonCard, "mutuals" | "mutual_count">): string {
  const [first, second] = card.mutuals;
  const others = card.mutual_count - card.mutuals.length;
  if (!first) return "";
  if (!second) return others > 0 ? `Seguito da @${first} e altri ${others}` : `Seguito da @${first}`;
  if (others > 0) return `Seguito da @${first}, @${second} e altri ${others}`;
  return `Seguito da @${first} e @${second}`;
}

/** Solo quanti: quali stili segue una persona resta privato. */
function stylesLine(count: number): string {
  return count === 1 ? "1 stile in comune" : `${count} stili in comune`;
}

/** La riga sotto il nickname: il motivo per cui la conosci o te la proponiamo. */
export function personLine(card: PersonCard): string {
  if (card.is_self) return "Sei tu";
  if (card.reason === "popular") return `Tra i più seguiti · ${followersLabel(card.followers)}`;
  if (card.follows_you && card.following !== "accepted") return "Ti segue";
  if (card.mutual_count > 0) return mutualLine(card);
  if (card.shared_style_count > 0) return stylesLine(card.shared_style_count);
  if (card.account_type === "business") return `Account business · ${followersLabel(card.followers)}`;
  return followersLabel(card.followers);
}

/** Il nickname diviso intorno a quello che hai scritto, per evidenziarlo. */
export function splitMatch(nickname: string, query: string): [string, string, string] {
  const at = query ? nickname.indexOf(query) : -1;
  if (at < 0) return [nickname, "", ""];
  return [nickname.slice(0, at), nickname.slice(at, at + query.length), nickname.slice(at + query.length)];
}
