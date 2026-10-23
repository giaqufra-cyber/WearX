/**
 * Cerca persone e suggerimenti (seduta 31). Segui e la X sui suggerimenti si vedono subito e
 * tornano come prima se il server dice no.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FollowState, PeopleResults, PeopleSuggestions, PersonCard } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { FEED_KEY } from "@/features/feed/api";
import { PORTFOLIO_KEY, userKey } from "@/features/portfolio/api";
import { PEOPLE_KEY, socialError } from "@/features/social/api";
import { apiGet, apiRequest } from "@/lib/api";

export const FIND_KEY = ["find-people"] as const;

function useToken() {
  const { session } = useAuth();
  return { token: session?.access_token, uid: session?.user.id };
}

const enc = encodeURIComponent;

export function searchKey(uid: string | undefined, query: string) {
  return [...FIND_KEY, uid, "search", query] as const;
}

export function suggestionsKey(uid: string | undefined) {
  return [...FIND_KEY, uid, "suggestions"] as const;
}

/** Risultati per `query` (già normalizzata). Vuota: nessuna richiesta. */
export function usePeopleSearch(query: string) {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: searchKey(uid, query),
    queryFn: ({ signal }) => apiGet<PeopleResults>(`/v1/people/search?q=${enc(query)}`, { token, signal }),
    enabled: Boolean(token) && query.length > 0,
    placeholderData: (previous) => previous,
    staleTime: 30_000,
  });
}

export function useSuggestions() {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: suggestionsKey(uid),
    queryFn: ({ signal }) => apiGet<PeopleSuggestions>("/v1/people/suggestions", { token, signal }),
    enabled: Boolean(token),
    staleTime: 60_000,
  });
}

type Lists = PeopleResults | PeopleSuggestions;

function patchCards(
  client: ReturnType<typeof useQueryClient>,
  update: (items: PersonCard[]) => PersonCard[],
) {
  const previous = client.getQueriesData<Lists>({ queryKey: FIND_KEY });
  client.setQueriesData<Lists>({ queryKey: FIND_KEY }, (data) => (data ? { ...data, items: update(data.items) } : data));
  return previous;
}

function restore(client: ReturnType<typeof useQueryClient>, previous: [readonly unknown[], Lists | undefined][]) {
  for (const [key, data] of previous) client.setQueryData(key, data);
}

/** Segui / ritira la richiesta da una riga della ricerca. */
export function useFollowFromList(options: { onError?: (message: string) => void } = {}) {
  const client = useQueryClient();
  const { token, uid } = useToken();
  const setState = (nickname: string, following: FollowState) =>
    patchCards(client, (items) => items.map((p) => (p.nickname === nickname ? { ...p, following } : p)));

  return useMutation({
    mutationFn: async ({ person, action }: { person: PersonCard; action: "follow" | "unfollow" }) => {
      if (action === "follow") {
        const path = `/v1/users/${enc(person.nickname)}/follow`;
        return (await apiRequest<{ following: FollowState }>("POST", path, { token })).following;
      }
      await apiRequest<void>("DELETE", `/v1/users/${enc(person.nickname)}/follow`, { token });
      return "none" as const;
    },
    onMutate: async ({ person, action }) => {
      await client.cancelQueries({ queryKey: FIND_KEY });
      // Un Business si segue subito; un privato passa a "richiesta inviata".
      const optimistic: FollowState =
        action === "unfollow" ? "none" : person.account_type === "business" ? "accepted" : "pending";
      return { previous: setState(person.nickname, optimistic) };
    },
    onSuccess: (following, { person }) => {
      setState(person.nickname, following);
      void client.invalidateQueries({ queryKey: userKey(uid, person.nickname) });
      void client.invalidateQueries({ queryKey: PORTFOLIO_KEY });
      void client.invalidateQueries({ queryKey: PEOPLE_KEY });
      void client.invalidateQueries({ queryKey: FEED_KEY });
    },
    onError: (error, _vars, context) => {
      if (context) restore(client, context.previous);
      options.onError?.(socialError(error));
    },
  });
}

/** "Non suggerirmelo più": sparisce subito dai suggerimenti. */
export function useDismissSuggestion(options: { onError?: (message: string) => void } = {}) {
  const client = useQueryClient();
  const { token, uid } = useToken();
  return useMutation({
    mutationFn: (nickname: string) =>
      apiRequest<void>("POST", `/v1/people/suggestions/${enc(nickname)}/dismiss`, { token }),
    onMutate: async (nickname) => {
      const key = suggestionsKey(uid);
      await client.cancelQueries({ queryKey: key });
      const previous = client.getQueryData<PeopleSuggestions>(key);
      client.setQueryData<PeopleSuggestions>(key, (data) =>
        data ? { ...data, items: data.items.filter((p) => p.nickname !== nickname) } : data,
      );
      return { previous };
    },
    onError: (error, _nickname, context) => {
      client.setQueryData(suggestionsKey(uid), context?.previous);
      options.onError?.(socialError(error));
    },
  });
}
