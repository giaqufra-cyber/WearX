/** Regole del modulo "Nuovo fit", allineate a quelle del server (sez. 6.4). */
import type { PostCreate, PostItemInput } from "@wearx/api-types";

export const MAX_PHOTOS = 10;
export const MAX_ITEMS = 8;
export const CAPTION_MAX = 140;
export const BRAND_MAX = 60;
export const NAME_MAX = 80;
const MAX_PRICE_CENTS = 10_000_000;

export type ItemDraft = { key: string; brand: string; name: string; price: string; link: string };
export type ItemErrors = Partial<Record<"brand" | "name" | "price" | "link", string>>;

/** "89" · "89,90" · "1.250,50" · "€ 1250.5" -> centesimi. null se vuoto, NaN se non è un prezzo. */
export function parsePrice(raw: string): number | null {
  let text = raw.replace(/[€\s]/g, "");
  if (!text) return null;
  if (!/^\d{1,3}([.,]?\d{3})*([.,]\d{1,2})?$|^\d+([.,]\d{1,2})?$/.test(text)) return Number.NaN;
  // L'ultimo separatore seguito da 1-2 cifre è quello dei decimali; gli altri sono migliaia.
  const decimal = text.match(/[.,](\d{1,2})$/);
  let cents = 0;
  if (decimal) {
    cents = Number(decimal[1]!.padEnd(2, "0"));
    text = text.slice(0, -decimal[0].length);
  }
  const euros = Number(text.replace(/[.,]/g, ""));
  const total = euros * 100 + cents;
  return total > MAX_PRICE_CENTS ? Number.NaN : total;
}

export function formatPrice(cents: number): string {
  const euros = Math.floor(cents / 100);
  const rest = cents % 100;
  const grouped = String(euros).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return rest ? `${grouped},${String(rest).padStart(2, "0")} €` : `${grouped} €`;
}

/** Stesse regole del server, per avvisare subito: solo https verso un sito vero. */
export function linkProblem(raw: string): string | null {
  const text = raw.trim();
  if (!text) return null;
  if (/\s/.test(text)) return "Il link non può contenere spazi.";
  if (!/^https:\/\//i.test(text)) return "Accettiamo solo link https.";
  const host = text.slice(8).split(/[/?#]/)[0] ?? "";
  if (host.includes("@")) return "Il link non è valido.";
  const name = host.replace(/:443$/, "");
  if (!name.includes(".") || /^[\d.]+$/.test(name) || name.includes(":")) return "Il link non è valido.";
  return null;
}

export function isItemEmpty(item: ItemDraft): boolean {
  return !item.brand.trim() && !item.name.trim() && !item.price.trim() && !item.link.trim();
}

export function itemErrors(item: ItemDraft): ItemErrors {
  if (isItemEmpty(item)) return {};
  const errors: ItemErrors = {};
  if (!item.brand.trim()) errors.brand = "Manca il brand.";
  else if (item.brand.trim().length > BRAND_MAX) errors.brand = `Massimo ${BRAND_MAX} caratteri.`;
  if (!item.name.trim()) errors.name = "Manca il capo.";
  else if (item.name.trim().length > NAME_MAX) errors.name = `Massimo ${NAME_MAX} caratteri.`;
  if (Number.isNaN(parsePrice(item.price))) errors.price = "Prezzo non valido (es. 89,90).";
  const link = linkProblem(item.link);
  if (link) errors.link = link;
  return errors;
}

export type PhotoState = "queued" | "preparing" | "uploading" | "processing" | "ready" | "error" | "rejected";

export type DraftForCheck = {
  photos: { status: PhotoState; uploadId?: string }[];
  style: string | null;
  items: ItemDraft[];
  caption: string;
};

export type PublishCheck = { ok: true } | { ok: false; reason: string };

export function canPublish(draft: DraftForCheck): PublishCheck {
  if (draft.photos.length === 0) return { ok: false, reason: "Scegli almeno una foto." };
  if (draft.photos.some((p) => p.status === "rejected")) {
    return { ok: false, reason: "Togli le foto che non possiamo pubblicare." };
  }
  if (draft.photos.some((p) => p.status === "error")) {
    return { ok: false, reason: "Una foto non si è caricata: tocca Riprova." };
  }
  if (draft.photos.some((p) => p.status !== "ready")) {
    const done = draft.photos.filter((p) => p.status === "ready").length;
    return { ok: false, reason: `Carichiamo le foto: ${done} di ${draft.photos.length}.` };
  }
  if (!draft.style) return { ok: false, reason: "Scegli lo stile del fit." };
  if (draft.items.some((i) => Object.keys(itemErrors(i)).length > 0)) {
    return { ok: false, reason: "Controlla i capi." };
  }
  if (draft.caption.trim().length > CAPTION_MAX) return { ok: false, reason: "Didascalia troppo lunga." };
  return { ok: true };
}

export function buildPostRequest(draft: DraftForCheck): PostCreate {
  const items: PostItemInput[] = draft.items
    .filter((i) => !isItemEmpty(i))
    .map((i) => {
      const price = parsePrice(i.price);
      return {
        brand: i.brand.trim(),
        name: i.name.trim(),
        price_cents: price === null || Number.isNaN(price) ? null : price,
        currency: "EUR",
        url: i.link.trim() || null,
      };
    });
  return {
    style: draft.style ?? "",
    caption: draft.caption.trim() || null,
    media: draft.photos.map((p) => p.uploadId ?? ""),
    items,
  };
}
