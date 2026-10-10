/**
 * Client Supabase dell'app. Si usa SOLO per l'autenticazione (e, dalla seduta 8, per
 * caricare foto con URL firmati rilasciati dall'API). Mai per leggere o scrivere tabelle:
 * tutti i dati passano dall'API di WearX (specifica, sez. 5).
 */
import { createClient } from "@supabase/supabase-js";
import { AppState, Platform } from "react-native";

import { env } from "@/lib/env";
import { largeSecureStore } from "@/lib/secureStorage";

function makeClient(url: string) {
  return createClient(url, env.supabasePublishableKey, {
    auth: {
      // Sul web (solo anteprima di sviluppo) si usa il localStorage del browser.
      storage: Platform.OS === "web" ? undefined : largeSecureStore,
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
      // PKCE: il link di conferma riporta nell'app un codice monouso, non i token. Il codice vale
      // solo insieme al segreto rimasto su questo telefono: un link intercettato non basta.
      flowType: "pkce",
    },
  });
}

// `let` e non `const`: nella demo il client si ricrea quando cambia il server (vedi useDemoServer).
// Chi importa `supabase` legge sempre il client attuale (gli import ES sono collegamenti vivi).
export let supabase = makeClient(env.supabaseUrl);

/** Solo demo: client verso il nuovo server. La sessione di ogni server resta separata. */
export function recreateSupabase(): void {
  void supabase.auth.stopAutoRefresh();
  supabase = makeClient(env.supabaseUrl);
}

// Il rinnovo automatico del token gira solo con l'app in primo piano.
if (Platform.OS !== "web") {
  AppState.addEventListener("change", (state) => {
    if (state === "active") {
      void supabase.auth.startAutoRefresh();
    } else {
      void supabase.auth.stopAutoRefresh();
    }
  });
}

/** Token di accesso attuale, da passare all'API di WearX. */
export async function getAccessToken(): Promise<string | undefined> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token;
}
