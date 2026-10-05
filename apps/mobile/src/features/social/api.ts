/**
 * Follow, richieste e blocchi. Il pulsante Segui e le decisioni sulle richieste si vedono subito
 * (aggiornamento ottimistico) e tornano com'erano se il server dice no.
 */
import { type InfiniteData, useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import type { FollowState, PeoplePage, UserProfile } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { FEED_KEY, POST_KEY } from "@/features/feed/api";
import { NOTIFICATIONS_KEY } from "@/features/notifications/keys";
import { PORTFOLIO_KEY, userKey } from "@/features/portfolio/api";
import { ApiError, apiGet, apiRequest } from "@/lib/api";

export const PEOPLE_KEY = ["people"] as const;
export type PeopleKind = "requests" | "followers" | "following" | "blocks";

const PATHS: Record<PeopleKind, string> = {
  requests: "/v1/me/follow-requests",
  followers: "/v1/me/followers",
  following: "/v1/me/following",
  blocks: "/v1/me/blocks",
};

function useToken() {
  const { session } = useAuth();
  return { token: session?.access_token, uid: session?.user.id };
}

const enc = encodeURIComponent;

export function peopleKey(uid: string | undefined, kind: PeopleKind) {
  return [...PEOPLE_KEY, uid, kind] as const;
}

export function usePeople(kind: PeopleKind) {
  const { token, uid } = useToken();
  return useInfiniteQuery({
    queryKey: peopleKey(uid, kind),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      apiGet<PeoplePage>(pageParam ? `${PATHS[kind]}?cursor=${enc(pageParam)}` : PATHS[kind], { token, signal }),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: Boolean(token),
  });
}

/** Testo del pulsante Segui nei suoi stati. */
export function followLabel(state: FollowState, followsYou: boolean): string {
  if (state === "accepted") return "Segui già";
  if (state === "pending") return "Richiesta inviata";
  return followsYou ? "Segui anche tu" : "Segui";
}

export const SOCIAL_ERRORS: Record<string, string> = {
  "user.not_found": "Questo profilo non è più disponibile.",
  "follow.self": "Non puoi seguire te stesso.",
  "follow.not_allowed": "Questa persona non può seguirti.",
  "follow.request_not_found": "La richiesta non c'è più.",
  "rate.limited": "Troppe azioni in poco tempo: riprova più tardi.",
};

export function socialError(error: unknown): string {
  const code = error instanceof ApiError ? error.code : "";
  return SOCIAL_ERRORS[code] ?? "Non riusciamo a raggiungere WearX. Controlla la connessione e riprova.";
}

/** Segui / smetti / ritira la richiesta, sul profilo di `nickname`. */
export function useFollow(nickname: string, options: { onError?: (message: string) => void } = {}) {
  const client = useQueryClient();
  const { token, uid } = useToken();
  const key = userKey(uid, nickname);

  const patch = (following: FollowState) =>
    client.setQueryData<UserProfile>(key, (user) =>
      user ? { ...user, relationship: { ...user.relationship, following } } : user,
    );

  return useMutation({
    mutationFn: async (action: "follow" | "unfollow") => {
      if (action === "follow") {
        return (await apiRequest<{ following: FollowState }>("POST", `/v1/users/${enc(nickname)}/follow`, { token }))
          .following;
      }
      await apiRequest<void>("DELETE", `/v1/users/${enc(nickname)}/follow`, { token });
      return "none" as const;
    },
    onMutate: async (action) => {
      await client.cancelQueries({ queryKey: key });
      const previous = client.getQueryData<UserProfile>(key);
      // Un Business si segue subito; un privato passa a "richiesta inviata".
      const optimistic: FollowState =
        action === "unfollow" ? "none" : previous?.account_type === "business" ? "accepted" : "pending";
      patch(optimistic);
      return { previous };
    },
    onSuccess: (following) => {
      patch(following);
      // Seguire o smettere cambia cosa si vede: portfolio, contatori, autori nel feed.
      void client.invalidateQueries({ queryKey: PORTFOLIO_KEY });
      void client.invalidateQueries({ queryKey: PEOPLE_KEY });
      void client.invalidateQueries({ queryKey: FEED_KEY });
    },
    onError: (error, _action, context) => {
      client.setQueryData(key, context?.previous);
      options.onError?.(socialError(error));
    },
  });
}

/** Togli una persona da un elenco in cache (decisione su una richiesta, rimozione...). */
function dropFromList(client: ReturnType<typeof useQueryClient>, uid: string | undefined, kind: PeopleKind, nickname: string) {
  const key = peopleKey(uid, kind);
  const previous = client.getQueryData<InfiniteData<PeoplePage>>(key);
  client.setQueryData<InfiniteData<PeoplePage>>(key, (data) =>
    data
      ? { ...data, pages: data.pages.map((p) => ({ ...p, items: p.items.filter((i) => i.nickname !== nickname) })) }
      : data,
  );
  return { key, previous };
}

/** Azioni sugli elenchi: accetta/rifiuta, togli un follower, smetti di seguire, sblocca. */
export function usePeopleAction(kind: PeopleKind, options: { onError?: (message: string) => void } = {}) {
  const client = useQueryClient();
  const { token, uid } = useToken();
  return useMutation({
    mutationFn: ({ nickname, accept }: { nickname: string; accept?: boolean }) => {
      if (kind === "requests") {
        return apiRequest<void>("POST", "/v1/me/follow-requests", {
          token,
          body: { nickname, decision: accept ? "accept" : "reject" },
        });
      }
      const path =
        kind === "followers"
          ? `/v1/me/followers/${enc(nickname)}`
          : kind === "following"
            ? `/v1/users/${enc(nickname)}/follow`
            : `/v1/users/${enc(nickname)}/block`;
      return apiRequest<void>("DELETE", path, { token });
    },
    onMutate: async ({ nickname }) => {
      await client.cancelQueries({ queryKey: peopleKey(uid, kind) });
      return dropFromList(client, uid, kind, nickname);
    },
    onError: (error, _vars, context) => {
      if (context) client.setQueryData(context.key, context.previous);
      options.onError?.(socialError(error));
    },
    onSettled: () => {
      void client.invalidateQueries({ queryKey: PEOPLE_KEY });
      void client.invalidateQueries({ queryKey: PORTFOLIO_KEY });
      // Una richiesta decisa cambia anche la lista delle notifiche.
      if (kind === "requests") void client.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    },
  });
}

export function useBlock(nickname: string) {
  const client = useQueryClient();
  const { token } = useToken();
  return useMutation({
    mutationFn: () => apiRequest<void>("PUT", `/v1/users/${enc(nickname)}/block`, { token }),
    onSuccess: () => {
      // La persona sparisce ovunque: profilo, griglia, feed, dettagli dei fit.
      for (const key of [PORTFOLIO_KEY, PEOPLE_KEY, FEED_KEY, POST_KEY, NOTIFICATIONS_KEY])
        void client.invalidateQueries({ queryKey: key });
    },
  });
}
