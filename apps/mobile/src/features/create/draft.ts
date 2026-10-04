/**
 * Bozza del nuovo fit, in memoria: resta mentre navighi nell'app (anche chiudendo la schermata),
 * sparisce dopo la pubblicazione o se la scarti.
 */
import { randomUUID } from "expo-crypto";
import { create } from "zustand";

import type { ItemDraft, PhotoState } from "@/features/create/form";

export type DraftPhoto = {
  localId: string;
  /** Anteprima locale (la foto scelta dalla galleria). */
  uri: string;
  width: number;
  height: number;
  status: PhotoState;
  /** 0-1 durante il caricamento. */
  progress: number;
  uploadId?: string;
  /** Motivo del rifiuto (server) o dell'errore (rete). */
  message?: string;
  attempts: number;
};

type Draft = {
  photos: DraftPhoto[];
  style: string | null;
  items: ItemDraft[];
  caption: string;
  /** Stessa chiave per tutti i tentativi di pubblicazione: il server non crea doppioni. */
  idempotencyKey: string;
  addPhotos: (photos: Pick<DraftPhoto, "uri" | "width" | "height">[]) => void;
  updatePhoto: (localId: string, patch: Partial<DraftPhoto>) => void;
  removePhoto: (localId: string) => void;
  movePhoto: (localId: string, delta: -1 | 1) => void;
  setStyle: (slug: string | null) => void;
  addItem: () => void;
  updateItem: (key: string, patch: Partial<ItemDraft>) => void;
  removeItem: (key: string) => void;
  setCaption: (caption: string) => void;
  reset: () => void;
};

const emptyItem = (): ItemDraft => ({ key: randomUUID(), brand: "", name: "", price: "", link: "" });

const initial = () => ({
  photos: [] as DraftPhoto[],
  style: null,
  items: [emptyItem()],
  caption: "",
  idempotencyKey: randomUUID(),
});

export const useNewPostDraft = create<Draft>((set) => ({
  ...initial(),
  addPhotos: (photos) =>
    set((state) => ({
      photos: [
        ...state.photos,
        ...photos.map((p) => ({ ...p, localId: randomUUID(), status: "queued" as const, progress: 0, attempts: 0 })),
      ].slice(0, 10),
    })),
  updatePhoto: (localId, patch) =>
    set((state) => ({ photos: state.photos.map((p) => (p.localId === localId ? { ...p, ...patch } : p)) })),
  removePhoto: (localId) => set((state) => ({ photos: state.photos.filter((p) => p.localId !== localId) })),
  movePhoto: (localId, delta) =>
    set((state) => {
      const photos = [...state.photos];
      const from = photos.findIndex((p) => p.localId === localId);
      const to = from + delta;
      if (from < 0 || to < 0 || to >= photos.length) return state;
      [photos[from], photos[to]] = [photos[to]!, photos[from]!];
      return { photos };
    }),
  setStyle: (style) => set({ style }),
  addItem: () => set((state) => (state.items.length >= 8 ? state : { items: [...state.items, emptyItem()] })),
  updateItem: (key, patch) =>
    set((state) => ({ items: state.items.map((i) => (i.key === key ? { ...i, ...patch } : i)) })),
  removeItem: (key) =>
    set((state) => {
      const items = state.items.filter((i) => i.key !== key);
      return { items: items.length ? items : [emptyItem()] };
    }),
  setCaption: (caption) => set({ caption }),
  reset: () => set(initial()),
}));

export function draftHasContent(draft: Pick<Draft, "photos" | "items" | "caption" | "style">): boolean {
  return (
    draft.photos.length > 0 ||
    draft.caption.trim() !== "" ||
    draft.items.some((i) => i.brand || i.name || i.price || i.link)
  );
}
