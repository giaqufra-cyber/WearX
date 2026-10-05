/** Testi del feed. */
import type { Post } from "@wearx/api-types";

import { formatPrice } from "@/features/create/form";

/** Iniziali per l'avatar: "fra.prova" -> "FP"; anonimo -> "". */
export function initials(nickname: string | undefined): string {
  if (!nickname) return "";
  const parts = nickname.split(/[._]/).filter(Boolean);
  const letters = parts.length > 1 ? parts[0]![0]! + parts[1]![0]! : nickname.slice(0, 2);
  return letters.toUpperCase();
}

/** "97% match" quando ci sono abbastanza conferme dello stile. */
export function matchLabel(match: number | null | undefined): string | null {
  return match === null || match === undefined ? null : `${Math.round(match * 100)}% match`;
}

/** Totale dei prezzi visibili (solo EUR), null se nessun prezzo. */
export function totalPrice(items: Post["items"]): string | null {
  const prices = items.filter((i) => i.price_cents !== null && i.currency === "EUR").map((i) => i.price_cents!);
  return prices.length ? formatPrice(prices.reduce((a, b) => a + b, 0)) : null;
}

export function votesLabel(count: number): string {
  return count === 1 ? "1 voto" : `${count.toLocaleString("it-IT")} voti`;
}

/** URL della variante più adatta alla larghezza in pixel fisici. */
export function bestVariant(variants: Record<string, string>, pixels: number): string | undefined {
  const widths = Object.keys(variants)
    .map(Number)
    .sort((a, b) => a - b);
  const pick = widths.find((w) => w >= pixels) ?? widths.at(-1);
  return pick === undefined ? undefined : variants[String(pick)];
}
