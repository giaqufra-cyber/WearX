/**
 * Recupero della password. Con il codice (o il link) Supabase apre già una sessione: finché la
 * nuova password non è salvata, l'app resta sulle schermate di accesso (`recovering`).
 */
import { create } from "zustand";

import { apiRequest } from "@/lib/api";
import { supabase } from "@/lib/supabase";

type RecoveryState = { recovering: boolean; start: () => void; finish: () => void };

export const useRecovery = create<RecoveryState>((set) => ({
  recovering: false,
  start: () => set({ recovering: true }),
  finish: () => set({ recovering: false }),
}));

/**
 * Nuova password: salvata su Supabase, poi fuori da tutti gli altri dispositivi (chi aveva la
 * vecchia password non resta dentro). Restituisce il codice d'errore Supabase, se c'è.
 */
export async function saveNewPassword(password: string): Promise<{ code?: unknown } | null> {
  const { error } = await supabase.auth.updateUser({ password });
  if (error) return error;
  await signOutOtherDevices();
  return null;
}

export async function signOutOtherDevices(): Promise<void> {
  // Supabase: niente più rinnovi per gli altri accessi. API: i loro token valgono zero da subito.
  await supabase.auth.signOut({ scope: "others" }).catch(() => undefined);
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (token) await apiRequest("POST", "/v1/me/devices/revoke-others", { token }).catch(() => undefined);
}
