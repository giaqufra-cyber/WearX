/**
 * Configurazione pubblica dell'app (variabili EXPO_PUBLIC_*).
 *
 * La chiave "publishable" di Supabase è pensata per stare dentro l'app: da sola non dà
 * accesso ai dati (le tabelle di WearX sono nello schema `app`, non esposto, con RLS).
 * Le chiavi segrete (secret / service_role) NON devono mai comparire qui.
 */

const DEFAULTS = {
  supabaseUrl: "https://alcpqfphwygpktrcyauu.supabase.co",
  supabasePublishableKey: "sb_publishable_8IepbDxDA7C0Gb9DF_GXsA_Gb5qUKp8",
  apiUrl: "http://localhost:8000",
} as const;

/**
 * Modalità demo (EXPO_PUBLIC_DEMO=1, `scripts/demo.sh` e build per Sideloadly): API e accesso finto
 * stanno su un unico indirizzo che cambia a ogni avvio della demo.
 * - Web: è l'indirizzo da cui è stata aperta la pagina.
 * - Telefono: lo sceglie la persona (link incollato o QR), vedi `features/demo`.
 */
const demo = process.env.EXPO_PUBLIC_DEMO === "1";

function webOrigin(): string | undefined {
  const location = (globalThis as { location?: { origin?: string } }).location;
  return typeof location?.origin === "string" && location.origin.startsWith("http") ? location.origin : undefined;
}

const demoWebOrigin = demo ? webOrigin() : undefined;

export const env = {
  demo,
  supabaseUrl: demoWebOrigin ?? process.env.EXPO_PUBLIC_SUPABASE_URL ?? DEFAULTS.supabaseUrl,
  supabasePublishableKey: process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? DEFAULTS.supabasePublishableKey,
  apiUrl: demoWebOrigin ?? process.env.EXPO_PUBLIC_API_URL ?? DEFAULTS.apiUrl,
  /** La registrazione col telefono richiede un fornitore SMS configurato su Supabase. */
  phoneSignupEnabled: process.env.EXPO_PUBLIC_PHONE_SIGNUP === "1",
  /**
   * Conferma email con codice a 6 cifre invece del link. Richiede l'SMTP personalizzato su
   * Supabase (senza, il modello dell'email non si può modificare e contiene solo il link).
   */
  emailOtp: demo || process.env.EXPO_PUBLIC_EMAIL_OTP === "1",
};

/** Solo demo: API e accesso finto passano al server indicato (stesso indirizzo per entrambi). */
export function setDemoServer(url: string): void {
  env.apiUrl = url;
  env.supabaseUrl = url;
}

if (/service_role|sb_secret_/i.test(env.supabasePublishableKey)) {
  // Errore volutamente bloccante: una chiave segreta dentro l'app sarebbe leggibile da chiunque.
  throw new Error("Chiave Supabase segreta nell'app: usa la chiave publishable.");
}
