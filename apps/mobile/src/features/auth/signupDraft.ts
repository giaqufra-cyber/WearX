/**
 * Bozza della registrazione, SOLO in memoria (mai salvata sul telefono).
 * La data di nascita serve per avviare la verifica dell'età (seduta 5) e poi si dimentica.
 */
import { create } from "zustand";

type Draft = {
  nickname: string;
  contactMode: "email" | "phone";
  /** Email o telefono E.164 usato per la registrazione: serve alla schermata del codice. */
  contact: string;
  birth: { day: number; month: number; year: number } | null;
  /** Scelte dell'onboarding (passi 3 e 4), fino alla creazione del profilo. */
  accountType: "private" | "business";
  set: (patch: Partial<Omit<Draft, "set" | "clear">>) => void;
  clear: () => void;
};

const initial = {
  nickname: "",
  contactMode: "email" as const,
  contact: "",
  birth: null,
  accountType: "private" as const,
};

export const useSignupDraft = create<Draft>((set) => ({
  ...initial,
  set: (patch) => set(patch),
  clear: () => set(initial),
}));
