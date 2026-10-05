/** Account Business: siti del negozio da verificare. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ShopDomain } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, apiGet, apiRequest } from "@/lib/api";

export const SHOPS_KEY = ["shop-domains"] as const;

function useToken() {
  const { session } = useAuth();
  return { token: session?.access_token, uid: session?.user.id };
}

export function useShopDomains(enabled = true) {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: [...SHOPS_KEY, uid],
    queryFn: ({ signal }) => apiGet<ShopDomain[]>("/v1/me/shop-domains", { token, signal }),
    enabled: Boolean(token) && enabled,
  });
}

export function useShopActions() {
  const client = useQueryClient();
  const { token, uid } = useToken();
  const refresh = () => void client.invalidateQueries({ queryKey: [...SHOPS_KEY, uid] });
  const enc = encodeURIComponent;
  return {
    add: useMutation({
      mutationFn: (domain: string) =>
        apiRequest<ShopDomain>("POST", "/v1/me/shop-domains", { token, body: { domain } }),
      onSuccess: refresh,
    }),
    verify: useMutation({
      mutationFn: (domain: string) =>
        apiRequest<ShopDomain>("POST", `/v1/me/shop-domains/${enc(domain)}/verify`, { token }),
      onSettled: refresh,
    }),
    remove: useMutation({
      mutationFn: (domain: string) => apiRequest<void>("DELETE", `/v1/me/shop-domains/${enc(domain)}`, { token }),
      onSettled: refresh,
    }),
  };
}

const MESSAGES: Record<string, string> = {
  "shop.taken": "Questo sito è già verificato da un altro account.",
  "shop.limit": "Puoi aggiungere al massimo 5 siti.",
  "link.invalid": "Scrivi un sito valido, per esempio tuonegozio.it.",
  "business.required": "Serve un account Business.",
  "rate.limited": "Troppi tentativi: riprova tra un po'.",
};

export function shopError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "shop.verify_failed") {
      const detail = typeof error.body?.detail === "string" ? error.body.detail : "";
      return `Verifica non riuscita. ${detail}`.trim();
    }
    return MESSAGES[error.code] ?? "Non è riuscito. Riprova.";
  }
  return "Non riusciamo a raggiungere WearX. Controlla la connessione.";
}
