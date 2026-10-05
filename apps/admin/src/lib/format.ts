/** Testi e calcoli del pannello (puri, testati). */

export const REASONS: Record<string, string> = {
  minor_safety: "Minore in pericolo",
  nudity: "Nudità o sesso",
  harassment: "Molestie o minacce",
  spam: "Spam",
  wrong_style: "Stile sbagliato",
  dangerous_link: "Link pericoloso",
  stolen_photo: "Foto rubata",
  other: "Altro",
};

export const GROUNDS: ReadonlyArray<{ value: string; label: string }> = [
  { value: "nudity", label: "Nudità o contenuti sessuali" },
  { value: "minor_safety", label: "Sicurezza dei minori" },
  { value: "harassment", label: "Molestie, minacce, dati personali" },
  { value: "spam", label: "Spam" },
  { value: "wrong_style", label: "Stile sbagliato" },
  { value: "dangerous_link", label: "Link pericoloso" },
  { value: "stolen_photo", label: "Foto di qualcun altro" },
  { value: "other", label: "Altra violazione" },
];

export const ACTIONS: Record<string, string> = {
  hide: "Nascosto",
  remove: "Rimosso",
  restyle: "Stile cambiato",
  suspend: "Sospeso",
  ban: "Account chiuso",
  restore: "Ripristinato",
  warn: "Avviso",
  limit_posting: "Pubblicazione sospesa",
};

export const PRIORITY_LABEL = ["P0", "P1", "P2"] as const;

export const APPEAL_STATUS: Record<string, string> = {
  open: "reclamo aperto",
  upheld: "reclamo respinto",
  reversed: "reclamo accolto",
};

export const POST_STATUS: Record<string, string> = {
  processing: "in elaborazione",
  active: "visibile",
  style_rejected: "fuori stile",
  hidden_moderation: "nascosto",
  deleted: "rimosso",
};

export const ACCOUNT_TYPE: Record<string, string> = { private: "personale", business: "business" };

/** Motivo prevalente di un gruppo di segnalazioni (il più grave, poi il più frequente). */
export function mainReason(reasons: Record<string, number>): string {
  const order = Object.keys(REASONS);
  return (
    Object.entries(reasons).sort(
      ([a, na], [b, nb]) => Number(b === "minor_safety") - Number(a === "minor_safety") || nb - na || order.indexOf(a) - order.indexOf(b),
    )[0]?.[0] ?? "other"
  );
}

/** "scade tra 40 min" / "scade tra 5 h" / "in ritardo di 2 h" */
export function dueLabel(dueIso: string, now: Date = new Date()): string {
  const minutes = Math.round((new Date(dueIso).getTime() - now.getTime()) / 60000);
  const span = (m: number) => (m < 60 ? `${m} min` : m < 48 * 60 ? `${Math.round(m / 60)} h` : `${Math.round(m / 1440)} g`);
  return minutes >= 0 ? `scade tra ${span(minutes)}` : `in ritardo di ${span(-minutes)}`;
}

export function dateTime(iso: string): string {
  return new Date(iso).toLocaleString("it-IT", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Scorciatoie della coda (sez. 14.3: "scorciatoie per decidere"). */
export type QueueCommand = "next" | "prev" | "dismiss" | "hide" | "remove" | "reveal" | "open";
const KEYS: Record<string, QueueCommand> = {
  j: "next",
  ArrowDown: "next",
  k: "prev",
  ArrowUp: "prev",
  a: "dismiss",
  n: "hide",
  r: "remove",
  v: "reveal",
  Enter: "open",
};

export function queueCommand(event: { key: string; target?: EventTarget | null; metaKey?: boolean; ctrlKey?: boolean; altKey?: boolean }): QueueCommand | null {
  if (event.metaKey || event.ctrlKey || event.altKey) return null;
  const el = event.target as HTMLElement | null;
  // Mentre si scrive una nota le lettere sono lettere.
  if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return null;
  return KEYS[event.key] ?? null;
}

/** Slug dal nome: "Après Ski" -> "apres-ski". */
export function slugify(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40);
}
