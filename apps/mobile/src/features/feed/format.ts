/** Testi del feed. */
import type { Post, VoteSummary } from "@wearx/api-types";

import { formatPrice } from "@/features/create/form";
import { locale, t, tn } from "@/lib/i18n";

/** Iniziali per l'avatar: "fra.prova" -> "FP"; anonimo -> "". */
export function initials(nickname: string | undefined): string {
  if (!nickname) return "";
  const parts = nickname.split(/[._]/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0]![0]! + parts[1]![0]! : nickname.slice(0, 2);
  return letters.toUpperCase();
}

/** "97% match" quando ci sono abbastanza conferme dello stile. */
export function matchLabel(match: number | null | undefined): string | null {
  return match === null || match === undefined ? null : t("{pct}% match", { pct: Math.round(match * 100) });
}

/** Totale dei prezzi visibili (solo EUR), null se nessun prezzo. */
export function totalPrice(items: Post["items"]): string | null {
  const prices = items.filter((i) => i.price_cents !== null && i.currency === "EUR").map((i) => i.price_cents!);
  return prices.length ? formatPrice(prices.reduce((a, b) => a + b, 0)) : null;
}

/**
 * Media e numero dei voti si aggiornano una volta all'ora (e la media da 5 voti): così nessuno
 * ricava il voto di una persona guardando come cambia la media.
 */
export function statsNote(vote: Pick<VoteSummary, "average_note" | "stats_updated_at">): string {
  const at = vote.stats_updated_at
    ? new Date(vote.stats_updated_at).toLocaleTimeString(locale(), { hour: "2-digit", minute: "2-digit" })
    : null;
  const when = at ? t("aggiornati alle {at}", { at }) : t("si aggiornano ogni ora");
  if (vote.average_note === "few_votes") return t("La media compare da 5 voti · {when}", { when });
  if (vote.average_note === "next_update") return t("Media in aggiornamento · {when}", { when });
  return at ? t("Voti aggiornati ogni ora · ultimo alle {at}", { at }) : t("Voti aggiornati ogni ora");
}

export function votesLabel(count: number): string {
  return tn(count, "{count} voto", "{count} voti");
}

/** URL della variante più adatta alla larghezza in pixel fisici. */
export function bestVariant(variants: Record<string, string>, pixels: number): string | undefined {
  const widths = Object.keys(variants)
    .map(Number)
    .sort((a, b) => a - b);
  const pick = widths.find((w) => w >= pixels) ?? widths.at(-1);
  return pick === undefined ? undefined : variants[String(pick)];
}
