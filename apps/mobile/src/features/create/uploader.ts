/**
 * Caricamento di una foto, con ripresa automatica:
 * prepara (JPEG, lato lungo max 2160 px) -> chiede il permesso firmato -> carica sull'archivio
 * con avanzamento -> conferma -> aspetta che il server la pulisca.
 * Se la rete cade si riprova da solo (1, 2, 4, 8 s); se il permesso firmato è scaduto se ne
 * chiede un altro. Gli errori definitivi (foto rifiutata dal server) non si riprovano.
 */
import type { MediaUpload } from "@wearx/api-types";

import { ApiError } from "@/lib/api";

export const RETRY_DELAYS_MS = [1000, 2000, 4000, 8000];
export const POLL_INTERVAL_MS = 1000;
export const POLL_MAX = 90;
export const MAX_SIDE = 2160;

export type PreparedFile = { uri: string; size: number; blob?: Blob };

export type UploadDeps = {
  prepare: (uri: string, width: number, height: number) => Promise<PreparedFile>;
  createUpload: (sizeBytes: number) => Promise<MediaUpload>;
  completeUpload: (uploadId: string) => Promise<MediaUpload>;
  getUpload: (uploadId: string) => Promise<MediaUpload>;
  sendFile: (
    target: NonNullable<MediaUpload["upload"]>,
    file: PreparedFile,
    onProgress: (fraction: number) => void,
    signal: AbortSignal,
  ) => Promise<void>;
  sleep: (ms: number, signal: AbortSignal) => Promise<void>;
};

export type UploadUpdate = {
  status: "preparing" | "uploading" | "processing" | "ready" | "error" | "rejected";
  progress?: number;
  uploadId?: string;
  message?: string;
};

export class UploadHttpError extends Error {
  constructor(readonly status: number) {
    super(`upload ${status}`);
  }
}

const REJECT_MESSAGES: Record<string, string> = {
  too_small: "Foto troppo piccola: serve almeno 320 px per lato.",
  bad_aspect_ratio: "Formato troppo stretto o troppo largo (massimo 2:1).",
  not_an_image: "Questo file non sembra una foto.",
  unsupported_format: "Formato non supportato.",
  too_many_pixels: "Foto troppo grande.",
  too_large: "Foto troppo pesante (massimo 15 MB).",
  blocked: "Questa foto non può essere pubblicata su WearX.",
  processing_error: "Non siamo riusciti a elaborare la foto. Riprova.",
  expired: "Caricamento scaduto. Riprova.",
};

export function rejectMessage(reason: string | null | undefined): string {
  return REJECT_MESSAGES[reason ?? ""] ?? "Questa foto non può essere usata.";
}

/** Errori che ha senso riprovare: rete, server sovraccarico, permesso scaduto. */
export function isRetryable(error: unknown): boolean {
  if (error instanceof UploadHttpError) return error.status === 403 || error.status === 408 || error.status >= 500;
  if (error instanceof ApiError) return error.status === 408 || error.status === 429 || error.status >= 500;
  return !(error instanceof DOMException && error.name === "AbortError");
}

class Rejected extends Error {
  constructor(readonly reason: string) {
    super(reason);
  }
}

async function attempt(
  photo: { uri: string; width: number; height: number },
  deps: UploadDeps,
  update: (u: UploadUpdate) => void,
  signal: AbortSignal,
): Promise<string> {
  update({ status: "preparing", progress: 0 });
  const file = await deps.prepare(photo.uri, photo.width, photo.height);
  const created = await deps.createUpload(file.size);
  update({ status: "uploading", progress: 0, uploadId: created.id });
  if (!created.upload) throw new Error("permesso di caricamento mancante");
  await deps.sendFile(created.upload, file, (p) => update({ status: "uploading", progress: p }), signal);
  update({ status: "processing", progress: 1 });
  let state = await deps.completeUpload(created.id);
  for (let i = 0; state.status === "processing" && i < POLL_MAX; i++) {
    await deps.sleep(POLL_INTERVAL_MS, signal);
    state = await deps.getUpload(created.id);
  }
  if (state.status === "rejected") throw new Rejected(state.reject_reason ?? "");
  if (state.status !== "ready") throw new Error("elaborazione troppo lunga");
  return created.id;
}

/** Porta una foto fino a "pronta" (o a un errore definitivo). Restituisce l'id del caricamento. */
export async function uploadPhoto(
  photo: { uri: string; width: number; height: number },
  deps: UploadDeps,
  update: (u: UploadUpdate) => void,
  signal: AbortSignal,
): Promise<string | null> {
  for (let tryNo = 0; ; tryNo++) {
    try {
      const id = await attempt(photo, deps, update, signal);
      update({ status: "ready", progress: 1, uploadId: id });
      return id;
    } catch (error) {
      if (signal.aborted) return null;
      if (error instanceof Rejected) {
        update({ status: "rejected", message: rejectMessage(error.reason) });
        return null;
      }
      if (error instanceof ApiError && error.code === "media.too_large") {
        update({ status: "rejected", message: rejectMessage("too_large") });
        return null;
      }
      const delay = RETRY_DELAYS_MS[tryNo];
      if (delay === undefined || !isRetryable(error)) {
        update({ status: "error", message: "Caricamento non riuscito. Controlla la connessione." });
        return null;
      }
      try {
        await deps.sleep(delay, signal);
      } catch {
        return null; // annullato durante l'attesa
      }
    }
  }
}
