/**
 * Portfolio dal server: profilo, griglia (a pagine), ordine, copertina, capsule, dettaglio fit.
 * Il riordino si vede subito (aggiornamento ottimistico) e torna com'era se il server dice no.
 */
import {
  type InfiniteData,
  type QueryClient,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import type { Capsule, PortfolioPage, Post, UserProfile } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { FEED_KEY, POST_KEY } from "@/features/feed/api";
import { ApiError, apiGet, apiRequest } from "@/lib/api";

export const PORTFOLIO_KEY = ["portfolio"] as const;
const PAGE_SIZE = 60;
const ALL = "*";

function useToken() {
  const { session } = useAuth();
  return { token: session?.access_token, uid: session?.user.id };
}

export function userKey(uid: string | undefined, nickname: string) {
  return [...PORTFOLIO_KEY, "user", uid, nickname] as const;
}

export function gridKey(uid: string | undefined, nickname: string, capsule: string | null) {
  return [...PORTFOLIO_KEY, "grid", uid, nickname, capsule ?? ALL] as const;
}

const notFound = (count: number, error: unknown) =>
  count < 2 && !(error instanceof ApiError && (error.status === 404 || error.status === 403));

export function useUser(nickname: string) {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: userKey(uid, nickname),
    queryFn: ({ signal }) => apiGet<UserProfile>(`/v1/users/${encodeURIComponent(nickname)}`, { token, signal }),
    enabled: Boolean(token) && nickname.length > 0,
    retry: notFound,
  });
}

export function usePortfolio(nickname: string, capsule: string | null, enabled = true) {
  const { token, uid } = useToken();
  return useInfiniteQuery({
    queryKey: gridKey(uid, nickname, capsule),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) => {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
      if (capsule) params.set("capsule", capsule);
      if (pageParam) params.set("cursor", pageParam);
      return apiGet<PortfolioPage>(`/v1/users/${encodeURIComponent(nickname)}/posts?${params}`, { token, signal });
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: enabled && Boolean(token) && nickname.length > 0,
    retry: notFound,
  });
}

// ---------- Ordine ----------

/** Nuovo ordine: `postId` subito dopo `afterId` (null = in testa). */
export function moveId(ids: string[], postId: string, afterId: string | null): string[] {
  const rest = ids.filter((id) => id !== postId);
  const at = afterId === null ? 0 : rest.indexOf(afterId) + 1;
  if (afterId !== null && at === 0) return ids; // vicino sconosciuto: nessun cambio
  return [...rest.slice(0, at), postId, ...rest.slice(at)];
}

/** Chi deve precedere il fit in posizione `index` dopo una freccia (‹ = -1, › = +1). */
export function afterIdForStep(ids: string[], index: number, step: -1 | 1): string | null | undefined {
  const target = index + step;
  if (target < 0 || target >= ids.length) return undefined; // già al bordo
  if (step === -1) return target === 0 ? null : ids[target - 1];
  return ids[target];
}

/** Applica il nuovo ordine alle pagine in cache mantenendo la loro lunghezza. */
export function reorderPages(
  data: InfiniteData<PortfolioPage>,
  postId: string,
  afterId: string | null,
): InfiniteData<PortfolioPage> {
  const tiles = data.pages.flatMap((p) => p.items);
  const byId = new Map(tiles.map((t) => [t.id, t]));
  const order = moveId(
    tiles.map((t) => t.id),
    postId,
    afterId,
  );
  let offset = 0;
  const cover = order[0] ?? null;
  return {
    ...data,
    pages: data.pages.map((page) => {
      const items = order.slice(offset, offset + page.items.length).map((id) => byId.get(id)!);
      offset += page.items.length;
      return { ...page, items, cover_id: cover };
    }),
  };
}

type Snapshot = [readonly unknown[], unknown][];

export const MOVE_KEY = ["portfolio-move"] as const;

export function useMoveFit(nickname: string, options: { onError?: (message: string) => void } = {}) {
  const client = useQueryClient();
  const { token, uid } = useToken();
  return useMutation({
    mutationKey: MOVE_KEY,
    mutationFn: ({ postId, afterId }: { postId: string; afterId: string | null }) =>
      apiRequest<void>("PUT", "/v1/me/portfolio/order", { token, body: { post_id: postId, after_id: afterId } }),
    onMutate: async ({ postId, afterId }) => {
      const key = gridKey(uid, nickname, null);
      await client.cancelQueries({ queryKey: key });
      const snapshot: Snapshot = client.getQueriesData({ queryKey: key });
      client.setQueryData<InfiniteData<PortfolioPage>>(key, (data) =>
        data ? reorderPages(data, postId, afterId) : data,
      );
      return { snapshot };
    },
    onError: (error, _vars, context) => {
      for (const [key, data] of context?.snapshot ?? []) client.setQueryData(key, data);
      options.onError?.(
        error instanceof ApiError && error.code === "rate.limited"
          ? "Troppi spostamenti in poco tempo: riprova tra un po'."
          : "L'ordine non è stato salvato. Controlla la connessione e riprova.",
      );
    },
    onSettled: () => {
      // Si riallinea con il server solo quando l'ultimo spostamento in corso è finito.
      if (client.isMutating({ mutationKey: MOVE_KEY }) <= 1) {
        void client.invalidateQueries({ queryKey: PORTFOLIO_KEY });
      }
    },
  });
}

// ---------- Capsule ----------

export const CAPSULE_ERRORS: Record<string, string> = {
  "capsule.name_taken": "Hai già una capsula con questo nome.",
  "capsule.limit": "Puoi avere al massimo 12 capsule.",
  "capsule.name_required": "Dai un nome alla capsula.",
  "capsule.not_found": "Questa capsula non esiste più.",
  "text.too_long": "Il nome può avere al massimo 30 caratteri.",
  "text.invalid_characters": "Il nome contiene caratteri non ammessi.",
};

export function capsuleError(error: unknown): string {
  const code = error instanceof ApiError ? error.code : "";
  return CAPSULE_ERRORS[code] ?? "Non riusciamo a salvare. Controlla la connessione e riprova.";
}

export function useCapsules(enabled = true) {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: [...PORTFOLIO_KEY, "capsules", uid],
    queryFn: ({ signal }) => apiGet<Capsule[]>("/v1/me/capsules", { token, signal }),
    enabled: enabled && Boolean(token),
  });
}

function refreshPortfolio(client: QueryClient) {
  void client.invalidateQueries({ queryKey: PORTFOLIO_KEY });
}

export function useCapsuleActions() {
  const client = useQueryClient();
  const { token } = useToken();
  const create = useMutation({
    mutationFn: (name: string) => apiRequest<Capsule>("POST", "/v1/me/capsules", { token, body: { name } }),
    onSuccess: () => refreshPortfolio(client),
  });
  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      apiRequest<Capsule>("PATCH", `/v1/me/capsules/${id}`, { token, body: { name } }),
    onSuccess: () => refreshPortfolio(client),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiRequest<void>("DELETE", `/v1/me/capsules/${id}`, { token }),
    onSuccess: () => refreshPortfolio(client),
  });
  return { create, rename, remove };
}

// ---------- Dettaglio del fit ----------

export function postKey(uid: string | undefined, id: string) {
  return [...POST_KEY, uid, id] as const;
}

export function usePost(id: string) {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: postKey(uid, id),
    queryFn: ({ signal }) => apiGet<Post>(`/v1/posts/${encodeURIComponent(id)}`, { token, signal }),
    enabled: Boolean(token) && id.length > 0,
    retry: notFound,
  });
}

export function usePostActions(id: string) {
  const client = useQueryClient();
  const { token, uid } = useToken();
  const setCapsule = useMutation({
    mutationFn: (capsuleId: string | null) =>
      apiRequest<Post>("PATCH", `/v1/posts/${id}`, { token, body: { capsule_id: capsuleId } }),
    onSuccess: (post) => {
      client.setQueryData(postKey(uid, id), post);
      refreshPortfolio(client);
    },
  });
  const remove = useMutation({
    mutationFn: () => apiRequest<void>("DELETE", `/v1/posts/${id}`, { token }),
    onSuccess: () => {
      client.removeQueries({ queryKey: postKey(uid, id) });
      refreshPortfolio(client);
      void client.invalidateQueries({ queryKey: FEED_KEY });
    },
  });
  return { setCapsule, remove };
}
