/**
 * Salvati e archivio (seduta 32). Salvare si vede subito sul fit (segnalibro pieno) e torna
 * com'era se il server dice no. Archiviare toglie il fit dal profilo e lo mette in Archivio.
 */
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import type { Post, TilePage } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { FEED_KEY, patchPost } from "@/features/feed/api";
import { PORTFOLIO_KEY, postKey } from "@/features/portfolio/api";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { useToast } from "@/ui/Toast";
import { t } from "@/lib/i18n";

export const SAVED_KEY = ["saved"] as const;
export const ARCHIVE_KEY = ["archive"] as const;

function useToken() {
  const { session } = useAuth();
  return { token: session?.access_token, uid: session?.user.id };
}

function useTiles(base: readonly string[], path: string) {
  const { token, uid } = useToken();
  return useInfiniteQuery({
    queryKey: [...base, uid],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      apiGet<TilePage>(pageParam ? `${path}?cursor=${encodeURIComponent(pageParam)}` : path, { token, signal }),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: Boolean(token),
  });
}

export const useSavedFits = () => useTiles(SAVED_KEY, "/v1/me/saved");
export const useArchivedFits = () => useTiles(ARCHIVE_KEY, "/v1/me/archive");

export function saveError(error: unknown): string {
  const code = error instanceof ApiError ? error.code : "";
  if (code === "post.not_found") return t("Questo fit non è più disponibile.");
  if (code === "rate.limited") return t("Hai salvato tantissimo in poco tempo: riprova più tardi.");
  return t("Non riusciamo a salvarlo. Controlla la connessione e riprova.");
}

/** Salva / togli dai salvati. */
export function useToggleSave(options: { onError?: (message: string) => void } = {}) {
  const client = useQueryClient();
  const { token } = useToken();
  return useMutation({
    mutationFn: async ({ postId, on }: { postId: string; on: boolean }) => {
      if (on) await apiRequest<{ saved: boolean }>("PUT", `/v1/posts/${postId}/save`, { token });
      else await apiRequest<void>("DELETE", `/v1/posts/${postId}/save`, { token });
      return on;
    },
    onMutate: ({ postId, on }) => ({ snapshot: patchPost(client, postId, (post) => ({ ...post, saved: on })) }),
    onSuccess: () => void client.invalidateQueries({ queryKey: SAVED_KEY }),
    onError: (error, _vars, context) => {
      for (const [key, data] of context?.snapshot ?? []) client.setQueryData(key, data);
      options.onError?.(saveError(error));
    },
  });
}

/** Il gesto del segnalibro, pronto per le card dei fit: salva o toglie, con un avviso. */
export function useSaveHandler(): (post: Post) => void {
  const toast = useToast();
  const { mutate } = useToggleSave({ onError: (message) => toast.show(message, { tone: "error" }) });
  return useCallback(
    (post: Post) =>
      mutate(
        { postId: post.id, on: !post.saved },
        { onSuccess: (on) => (on ? toast.show(t("Salvato. Lo ritrovi nel tuo profilo, in Salvati.")) : undefined) },
      ),
    [mutate, toast],
  );
}

/** Archivia / rimetti nel profilo un tuo fit. */
export function useArchive(id: string) {
  const client = useQueryClient();
  const { token, uid } = useToken();
  return useMutation({
    mutationFn: (on: boolean) => apiRequest<Post>(on ? "POST" : "DELETE", `/v1/posts/${id}/archive`, { token }),
    onSuccess: (post) => {
      client.setQueryData(postKey(uid, id), post);
      void client.invalidateQueries({ queryKey: PORTFOLIO_KEY });
      void client.invalidateQueries({ queryKey: ARCHIVE_KEY });
      void client.invalidateQueries({ queryKey: FEED_KEY });
    },
  });
}
