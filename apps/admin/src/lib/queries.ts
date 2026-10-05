"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Lettura dall'API con il token dello staff. La chiave di cache è il percorso. */
export function useStaffQuery<T>(path: string | null, options: { refetchInterval?: number } = {}) {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["admin", path],
    queryFn: () => api<T>("GET", path!, token!),
    enabled: Boolean(token && path),
    refetchInterval: options.refetchInterval,
  });
}

type Method = "POST" | "PUT" | "PATCH" | "DELETE";

/**
 * Scrittura: alla fine si ricaricano tutti i dati del pannello (sono pochi e devono essere freschi).
 * `payload` sceglie cosa mandare all'API (l'id o il nickname vanno nel percorso, non nel corpo:
 * l'API rifiuta campi in più).
 */
export function useStaffMutation<TBody, TResult = unknown>(
  method: Method,
  path: (body: TBody) => string,
  payload: (body: TBody) => unknown = (body) => body,
) {
  const { token } = useAuth();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: TBody) =>
      api<TResult>(method, path(body), token!, method === "DELETE" ? undefined : payload(body)),
    onSettled: () => void client.invalidateQueries({ queryKey: ["admin"] }),
  });
}
