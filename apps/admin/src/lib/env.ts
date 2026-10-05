/**
 * Configurazione pubblica del pannello (NEXT_PUBLIC_*). La chiave "publishable" di Supabase è
 * pubblica per definizione; una chiave segreta qui sarebbe leggibile da chiunque apra la pagina.
 */
export const env = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
  supabaseUrl: process.env.NEXT_PUBLIC_SUPABASE_URL ?? "https://alcpqfphwygpktrcyauu.supabase.co",
  supabaseKey: process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "sb_publishable_8IepbDxDA7C0Gb9DF_GXsA_Gb5qUKp8",
  /** Accesso incollando un token: SOLO in sviluppo, mai in produzione. */
  devLogin: process.env.NODE_ENV === "development" && process.env.NEXT_PUBLIC_ADMIN_DEV_LOGIN === "1",
};

if (/service_role|sb_secret_/i.test(env.supabaseKey)) {
  throw new Error("Chiave Supabase segreta nel pannello: usa la chiave publishable.");
}
