import type { ConfigContext, ExpoConfig } from "expo/config";

/**
 * Configurazione dinamica sopra app.json (seduta 25): solo controlli, nessun valore nuovo.
 * Una build per gli store (profili "beta" e "production" di eas.json) deve parlare con un'API
 * vera in https: se manca l'indirizzo si ferma subito, invece di produrre un'app che cerca
 * "localhost" sul telefono dei tester.
 */
const STORE_PROFILES = ["beta", "production"];

export default ({ config }: ConfigContext): ExpoConfig => {
  const profile = process.env.EAS_BUILD_PROFILE;
  if (profile && STORE_PROFILES.includes(profile)) {
    const api = process.env.EXPO_PUBLIC_API_URL ?? "";
    if (!api.startsWith("https://")) {
      throw new Error(
        `Build "${profile}" senza EXPO_PUBLIC_API_URL in https (ora: "${api}"). ` +
          "Impostala nelle variabili d'ambiente del progetto su expo.dev (docs/BETA.md).",
      );
    }
    if (/service_role|sb_secret_/i.test(process.env.EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? "")) {
      throw new Error("Chiave Supabase segreta tra le variabili dell'app: usa la chiave publishable.");
    }
  }
  return config as ExpoConfig;
};
