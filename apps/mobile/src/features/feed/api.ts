/**
 * Feed e voti dal server. Il voto si vede subito (aggiornamento ottimistico) e il post resta
 * nella pagina mostrando la media; se il server rifiuta, si torna com'era.
 */
import { type InfiniteData, type QueryClient, useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { FeedPage, Post, VoteSummary } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, apiGet, apiRequest } from "@/lib/api";

export const FEED_KEY = ["feed"] as const;

export function feedKey(uid: string | undefined, style: string | null) {
  return [...FEED_KEY, uid, style ?? "*"] as const;
}

export function useFeed(style: string | null) {
  const { session } = useAuth();
  const token = session?.access_token;
  const client = useQueryClient();
  const key = feedKey(session?.user.id, style);
  return useInfiniteQuery({
    queryKey: key,
    initialPageParam: null as string | null,
    queryFn: async ({ pageParam, signal }) => {
      const params = new URLSearchParams();
      if (style) params.set("style", style);
      if (pageParam) params.set("cursor", pageParam);
      const query = params.toString();
      try {
        return await apiGet<FeedPage>(`/v1/feed${query ? `?${query}` : ""}`, { token, signal });
      } catch (error) {
        if (error instanceof ApiError && error.code === "feed.cursor_expired") {
          // La sessione del feed è scaduta (app aperta a lungo): si riparte dall'inizio.
          void client.resetQueries({ queryKey: key });
        }
        throw error;
      }
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: Boolean(token),
    staleTime: 5 * 60_000,
  });
}

type Snapshot = [readonly unknown[], unknown][];

/** Applica una modifica al riepilogo del voto di un post in tutte le pagine di feed in cache. */
export function patchVote(client: QueryClient, postId: string, patch: (vote: VoteSummary) => VoteSummary): Snapshot {
  const snapshot = client.getQueriesData({ queryKey: FEED_KEY });
  for (const [key, data] of snapshot) {
    const feed = data as InfiniteData<FeedPage> | undefined;
    if (!feed?.pages) continue;
    client.setQueryData(key, {
      ...feed,
      pages: feed.pages.map((page) => ({
        ...page,
        items: page.items.map((post: Post) => (post.id === postId ? { ...post, vote: patch(post.vote) } : post)),
      })),
    });
  }
  return snapshot;
}

export const VOTE_ERRORS: Record<string, string> = {
  "vote.own_post": "Non puoi votare i tuoi fit.",
  "post.not_found": "Questo fit non è più disponibile.",
  "vote.not_allowed": "Questo fit non si può votare.",
  "rate.limited": "Hai votato tantissimo in poco tempo: riprova tra un po'.",
};

export function useVote(options: { onError?: (message: string) => void } = {}) {
  const client = useQueryClient();
  const { session } = useAuth();
  const token = session?.access_token;
  return useMutation({
    mutationFn: ({ postId, score, styleConfirm }: { postId: string; score: number; styleConfirm: boolean | null }) =>
      apiRequest<VoteSummary>("PUT", `/v1/posts/${postId}/vote`, {
        token,
        body: styleConfirm === null ? { score } : { score, style_confirm: styleConfirm },
      }),
    onMutate: async ({ postId, score, styleConfirm }) => {
      await client.cancelQueries({ queryKey: FEED_KEY });
      // Subito: il tuo voto è registrato; la media arriva con la risposta del server.
      const snapshot = patchVote(client, postId, (vote) => ({
        ...vote,
        mine: score,
        my_style_confirm: vote.ask_style_confirm ? styleConfirm : vote.my_style_confirm,
        ask_style_confirm: false,
      }));
      return { snapshot };
    },
    onSuccess: (summary, { postId }) => {
      patchVote(client, postId, () => summary);
    },
    onError: (error, _vars, context) => {
      for (const [key, data] of context?.snapshot ?? []) client.setQueryData(key, data);
      const code = error instanceof ApiError ? error.code : "";
      options.onError?.(VOTE_ERRORS[code] ?? "Il voto non è arrivato. Controlla la connessione e riprova.");
    },
  });
}
