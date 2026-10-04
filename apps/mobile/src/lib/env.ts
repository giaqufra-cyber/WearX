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

export const env = {
  supabaseUrl: process.env.EXPO_PUBLIC_SUPABASE_URL ?? DEFAULTS.supabaseUrl,
  supabasePublishableKey: process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? DEFAULTS.supabasePublishableKey,
  apiUrl: process.env.EXPO_PUBLIC_API_URL ?? DEFAULTS.apiUrl,
  /** La registrazione col telefono richiede un fornitore SMS configurato su Supabase. */
  phoneSignupEnabled: process.env.EXPO_PUBLIC_PHONE_SIGNUP === "1",
  /**
   * Conferma email con codice a 6 cifre invece del link. Richiede l'SMTP personalizzato su
   * Supabase (senza, il modello dell'email non si può modificare e contiene solo il link).
   */
  emailOtp: process.env.EXPO_PUBLIC_EMAIL_OTP === "1",
};

if (/service_role|sb_secret_/i.test(env.supabasePublishableKey)) {
  // Errore volutamente bloccante: una chiave segreta dentro l'app sarebbe leggibile da chiunque.
  throw new Error("Chiave Supabase segreta nell'app: usa la chiave publishable.");
}
