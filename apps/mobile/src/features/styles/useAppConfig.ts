import { useQuery } from "@tanstack/react-query";

import type { AppConfig } from "@wearx/api-types";

import { apiGet } from "@/lib/api";
import { language } from "@/lib/i18n";

/**
 * Indirizzo della configurazione: la lingua va anche nell'indirizzo perché la risposta può
 * restare in cache sul telefono fino a 5 minuti (nomi degli stili e link legali cambiano).
 */
export function configPath(): string {
  return `/v1/config?lang=${language()}`;
}

/** Configurazione pubblica (stili attivi, flag, link legali). Si aggiorna ogni 5 minuti. */
export function useAppConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<AppConfig>(configPath()),
    staleTime: 5 * 60_000,
  });
}
