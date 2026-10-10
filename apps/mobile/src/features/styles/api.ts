/**
 * Stili dal server: elenco e ricerca, pagina dello stile, i tuoi stili, entrare e uscire.
 * Entrare/uscire si vede subito (aggiornamento ottimistico) e si annulla se il server dice no.
 */
import { type QueryClient, useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { StyleCard, StyleDetail, StyleList, StylePostsPage } from "@wearx/api-types";

import { ME_QUERY_KEY, useAuth } from "@/features/auth/AuthProvider";
import { ApiError, apiGet, apiRequest } from "@/lib/api";

export const STYLES_KEY = ["styles"] as const;

function useToken() {
  const { session } = useAuth();
  return { token: session?.access_token, uid: session?.user.id };
}

export function useStyles(query: string) {
  const { token, uid } = useToken();
  const q = query.trim();
  return useQuery({
    queryKey: [...STYLES_KEY, "list", uid, q],
    queryFn: ({ signal }) =>
      apiGet<StyleList>(q ? `/v1/styles?q=${encodeURIComponent(q)}` : "/v1/styles", { token, signal }),
    enabled: Boolean(token),
    // Mentre arriva il risultato della nuova ricerca resta visibile quello precedente.
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  });
}

export function useMyStyles() {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: [...STYLES_KEY, "mine", uid],
    queryFn: ({ signal }) => apiGet<StyleList>("/v1/me/styles", { token, signal }),
    enabled: Boolean(token),
    staleTime: 60_000,
  });
}

export function useStyle(slug: string) {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: [...STYLES_KEY, "detail", uid, slug],
    queryFn: ({ signal }) => apiGet<StyleDetail>(`/v1/styles/${encodeURIComponent(slug)}`, { token, signal }),
    enabled: Boolean(token) && slug.length > 0,
    retry: (count, error) => count < 2 && !(error instanceof ApiError && error.status === 404),
  });
}

export type StyleSort = "top" | "new";

/**
 * I fit di uno stile, a pagine (seduta 26). Sotto STYLES_KEY: pubblicare un fit ricarica anche
 * questa griglia (new-post invalida gli stili).
 */
export function useStylePosts(slug: string, sort: StyleSort) {
  const { token, uid } = useToken();
  return useInfiniteQuery({
    queryKey: [...STYLES_KEY, "posts", uid, slug, sort],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => {
      const params = new URLSearchParams({ sort, limit: "24" });
      if (pageParam) params.set("cursor", pageParam);
      return apiGet<StylePostsPage>(`/v1/styles/${encodeURIComponent(slug)}/posts?${params}`, { token, signal });
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: Boolean(token) && slug.length > 0,
    retry: (count, error) => count < 2 && !(error instanceof ApiError && error.status === 404),
  });
}

type Snapshot = [readonly unknown[], unknown][];

/** Applica entrata/uscita a tutte le copie dello stile in cache (liste, pagina, i tuoi stili). */
function applyMembership(client: QueryClient, slug: string, join: boolean): Snapshot {
  const snapshot = client.getQueriesData({ queryKey: STYLES_KEY });
  const patch = <T extends StyleCard>(card: T): T =>
    card.slug !== slug || card.joined === join
      ? card
      : { ...card, joined: join, member_count: Math.max(0, card.member_count + (join ? 1 : -1)) };

  let joinedCard: StyleCard | undefined;
  for (const [key, data] of snapshot) {
    if (!data) continue;
    if (key[1] === "detail") {
      const updated = patch(data as StyleDetail);
      if (updated.slug === slug) joinedCard = updated;
      client.setQueryData(key, updated);
    } else if (key[1] === "list") {
      const list = data as StyleList;
      const items = list.items.map(patch);
      joinedCard ??= items.find((s) => s.slug === slug);
      client.setQueryData(key, { ...list, items });
    }
  }
  for (const [key, data] of snapshot) {
    if (key[1] !== "mine" || !data) continue;
    const mine = data as StyleList;
    const items = join
      ? joinedCard && !mine.items.some((s) => s.slug === slug)
        ? [...mine.items, { ...joinedCard, joined: true }]
        : mine.items
      : mine.items.filter((s) => s.slug !== slug);
    client.setQueryData(key, { items, total: items.length });
  }
  return snapshot;
}

export const MEMBERSHIP_ERRORS: Record<string, string> = {
  "style.last_membership": "Resta almeno in uno stile: il tuo feed è fatto di questi.",
  "style.limit": "Hai raggiunto il massimo di stili. Esci da uno per entrare in un altro.",
  "style.not_found": "Questo stile non è più disponibile.",
  "rate.limited": "Troppi cambi in poco tempo. Riprova tra un po'.",
};

export function membershipErrorMessage(error: unknown): string {
  const code = error instanceof ApiError ? error.code : "";
  return MEMBERSHIP_ERRORS[code] ?? "Non riusciamo a salvare la modifica. Controlla la connessione e riprova.";
}

export function useMembership(options: { onError?: (message: string) => void } = {}) {
  const client = useQueryClient();
  const { token } = useToken();
  return useMutation({
    mutationFn: ({ slug, join }: { slug: string; join: boolean }) =>
      apiRequest<StyleCard>(join ? "PUT" : "DELETE", `/v1/styles/${encodeURIComponent(slug)}/membership`, {
        token,
      }),
    onMutate: async ({ slug, join }) => {
      await client.cancelQueries({ queryKey: STYLES_KEY });
      return { snapshot: applyMembership(client, slug, join) };
    },
    onError: (error, _vars, context) => {
      for (const [key, data] of context?.snapshot ?? []) client.setQueryData(key, data);
      options.onError?.(membershipErrorMessage(error));
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: STYLES_KEY });
      void client.invalidateQueries({ queryKey: ME_QUERY_KEY });
    },
  });
}
