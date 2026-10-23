/**
 * Due lingue, italiano e inglese (sedute 33-34).
 *
 * Il testo italiano scritto nel codice È la chiave: `t("Segui")` mostra "Segui" in italiano e
 * "Follow" in inglese (dizionario in `src/i18n/en.ts`). Se manca una traduzione resta l'italiano;
 * un test controlla che non ne manchi nessuna.
 *
 * - Lingua: quella del telefono (italiano se è italiano, altrimenti inglese) oppure quella scelta
 *   in Privacy e sicurezza → Lingua. Cambiandola l'app si ridisegna da capo.
 * - Testi in costanti fuori dai componenti: si segnano con `N_("...")` (non traduce, serve solo
 *   al controllo) e si traducono dove si mostrano con `t(costante)`.
 * - Segnaposto tra graffe: `t("Ora segui @{nick}.", { nick })`.
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { getLocales } from "expo-localization";
import { create } from "zustand";

import { EN } from "@/i18n/en";

export type Lang = "it" | "en";
export type LangChoice = Lang | "auto";

const STORAGE_KEY = "wearx.language";

/** La lingua del telefono: italiano se è italiano, altrimenti inglese. */
export function phoneLanguage(): Lang {
  try {
    return getLocales()[0]?.languageCode === "it" ? "it" : "en";
  } catch {
    return "it";
  }
}

let current: Lang = phoneLanguage();

export function language(): Lang {
  return current;
}

/** Per date e numeri (`toLocaleDateString` e simili). */
export function locale(): string {
  return current === "en" ? "en-GB" : "it-IT";
}

type Params = Record<string, string | number>;

function fill(text: string, params?: Params): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in params ? String(params[name]) : match));
}

/** Traduce un testo italiano nella lingua attuale. */
export function t(source: string, params?: Params): string {
  const text = current === "en" ? (EN[source] ?? source) : source;
  return fill(text, params);
}

/** Singolare o plurale secondo `count` (in italiano e inglese basta "uno" / "altri"). */
export function tn(count: number, one: string, other: string, params?: Params): string {
  return t(count === 1 ? one : other, { count: formatCount(count), ...params });
}

/** Segna un testo da tradurre senza tradurlo ora (costanti fuori dai componenti). */
export function N_(source: string): string {
  return source;
}

/** 1.200 in italiano, 1,200 in inglese (a mano: non tutti i telefoni hanno le regole). */
export function formatCount(count: number): string {
  return String(count).replace(/\B(?=(\d{3})+(?!\d))/g, current === "en" ? "," : ".");
}

type LanguageState = {
  choice: LangChoice;
  lang: Lang;
  setChoice: (choice: LangChoice) => void;
};

export const useLanguage = create<LanguageState>((set) => ({
  choice: "auto",
  lang: current,
  setChoice: (choice) => {
    current = choice === "auto" ? phoneLanguage() : choice;
    set({ choice, lang: current });
    void AsyncStorage.setItem(STORAGE_KEY, choice).catch(() => undefined);
  },
}));

/** All'avvio: la scelta salvata sul telefono, se c'è. */
export async function loadLanguageChoice(): Promise<void> {
  try {
    const saved = await AsyncStorage.getItem(STORAGE_KEY);
    if (saved === "it" || saved === "en" || saved === "auto") {
      current = saved === "auto" ? phoneLanguage() : saved;
      useLanguage.setState({ choice: saved, lang: current });
    }
  } catch {
    // Senza memoria resta la lingua del telefono.
  }
}

/** Solo per i test. */
export function setLanguageForTests(lang: Lang): void {
  current = lang;
  useLanguage.setState({ choice: lang, lang });
}
