import { useQuery } from "@tanstack/react-query";

import { apiGet, type AppConfig } from "@/lib/api";

/** Configurazione pubblica (stili attivi, flag, link legali). Si aggiorna ogni 5 minuti. */
export function useAppConfig() {
  return useQuery({
    queryKey: ["config"],
    queryFn: () => apiGet<AppConfig>("/v1/config"),
    staleTime: 5 * 60_000,
  });
}
