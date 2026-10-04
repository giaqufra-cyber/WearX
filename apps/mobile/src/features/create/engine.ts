/** Motore dei caricamenti: due foto alla volta, in ordine, annullabili. */
import { useEffect } from "react";

import { useNewPostDraft } from "@/features/create/draft";
import { type UploadDeps, uploadPhoto } from "@/features/create/uploader";

export const MAX_PARALLEL = 2;

const running = new Map<string, AbortController>();

export function useUploadEngine(deps: UploadDeps | null) {
  const photos = useNewPostDraft((s) => s.photos);

  useEffect(() => {
    if (!deps) return;
    const store = useNewPostDraft.getState();
    const queued = photos.filter((p) => p.status === "queued" && !running.has(p.localId));
    const free = MAX_PARALLEL - running.size;
    for (const photo of queued.slice(0, Math.max(0, free))) {
      const controller = new AbortController();
      running.set(photo.localId, controller);
      store.updatePhoto(photo.localId, { status: "preparing", attempts: photo.attempts + 1, message: undefined });
      void uploadPhoto(
        photo,
        deps,
        (update) => {
          if (!controller.signal.aborted) useNewPostDraft.getState().updatePhoto(photo.localId, update);
        },
        controller.signal,
      ).finally(() => {
        running.delete(photo.localId);
        // Libera il posto: la prossima foto in coda parte.
        useNewPostDraft.getState().updatePhoto(photo.localId, {});
      });
    }
  }, [photos, deps]);
}

export function cancelUpload(localId: string) {
  running.get(localId)?.abort();
  running.delete(localId);
}

export function cancelAllUploads() {
  for (const controller of running.values()) controller.abort();
  running.clear();
}

export function retryPhoto(localId: string) {
  useNewPostDraft.getState().updatePhoto(localId, { status: "queued", progress: 0, message: undefined });
}
