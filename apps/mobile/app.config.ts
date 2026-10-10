import type { ConfigContext, ExpoConfig } from "expo/config";
import { withEntitlementsPlist } from "expo/config-plugins";

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
  if (process.env.EXPO_PUBLIC_DEMO === "1") return demoConfig(config as ExpoConfig);
  return config as ExpoConfig;
};

/**
 * Build demo (EXPO_PUBLIC_DEMO=1) da installare con Sideloadly e un Apple ID gratuito: un account
 * gratuito non può firmare app con App Attest né con le notifiche push, quindi la build demo non
 * le dichiara. Nome e identificativo diversi: non si confonde con l'app vera.
 */
function demoConfig(config: ExpoConfig): ExpoConfig {
  const entitlements = { ...(config.ios?.entitlements ?? {}) };
  delete entitlements["com.apple.developer.devicecheck.appattest-environment"];
  const demo: ExpoConfig = {
    ...config,
    name: "WearX Demo",
    ios: { ...config.ios, bundleIdentifier: "app.wearx.mobile.demo", entitlements },
    plugins: (config.plugins ?? []).filter(
      (plugin) => (Array.isArray(plugin) ? plugin[0] : plugin) !== "expo-notifications",
    ),
  };
  // expo-notifications aggiunge comunque l'entitlement dei push ("aps-environment"): via.
  return withEntitlementsPlist(demo, (mod) => {
    delete mod.modResults["aps-environment"];
    delete mod.modResults["com.apple.developer.devicecheck.appattest-environment"];
    return mod;
  });
}
