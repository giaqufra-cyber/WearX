/**
 * Catalogo degli stili (seduta 29): categorie e ricerca locale.
 * Il server manda gli stili già ordinati dai più seguiti; qui si filtra senza cambiare l'ordine.
 */
import type { StyleCard } from "@wearx/api-types";

export type StyleCategory = NonNullable<StyleCard["category"]>;

export const CATEGORIES: { key: StyleCategory; label: string }[] = [
  { key: "stili", label: "Stili" },
  { key: "sport", label: "Sport" },
  { key: "accessori", label: "Accessori" },
  { key: "beauty", label: "Beauty" },
  { key: "sottoculture", label: "Sottoculture" },
  { key: "occasioni", label: "Occasioni" },
];

/** Minuscole e senza accenti: "Galà" e "gala" sono la stessa parola. */
export function fold(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();
}

type Searchable = { slug: string; name: string; tagline: string; category?: string | null };

export function inCategory<T extends Searchable>(styles: T[], category: StyleCategory | null): T[] {
  return category ? styles.filter((s) => (s.category ?? "stili") === category) : styles;
}

/** Ricerca per nome, descrizione e categoria: prima chi inizia con il testo, poi gli altri. */
export function searchStyles<T extends Searchable>(styles: T[], query: string): T[] {
  const q = fold(query);
  if (!q) return styles;
  const label = (s: T) => CATEGORIES.find((c) => c.key === (s.category ?? "stili"))?.label ?? "";
  const hits = styles.filter((s) => fold(`${s.name} ${s.tagline} ${label(s)}`).includes(q));
  const starts = hits.filter((s) => fold(s.name).startsWith(q) || fold(s.name).includes(` ${q}`));
  return [...starts, ...hits.filter((s) => !starts.includes(s))];
}

/**
 * Stili da mostrare quando pubblichi: senza ricerca, quello scelto, poi i tuoi, poi i più
 * seguiti, fino a `limit`; con la ricerca, tutti i risultati.
 */
export function styleChoices<T extends Searchable>(
  all: T[],
  mine: T[],
  query: string,
  selected: string | null,
  limit: number,
): { items: T[]; more: number } {
  if (fold(query)) return { items: searchStyles(all, query), more: 0 };
  const ordered: T[] = [];
  const add = (style: T | undefined) => {
    if (style && !ordered.some((s) => s.slug === style.slug)) ordered.push(style);
  };
  add(all.find((s) => s.slug === selected) ?? mine.find((s) => s.slug === selected));
  mine.forEach(add);
  all.forEach(add);
  return { items: ordered.slice(0, limit), more: Math.max(0, ordered.length - limit) };
}
