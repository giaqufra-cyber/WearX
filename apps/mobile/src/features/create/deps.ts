/** Implementazioni reali delle dipendenze del caricamento (rete, archivio, ritaglio). */
import type { MediaUpload } from "@wearx/api-types";
import { ImageManipulator, SaveFormat } from "expo-image-manipulator";
import { Platform } from "react-native";

import { MAX_SIDE, type PreparedFile, UploadHttpError, type UploadDeps } from "@/features/create/uploader";
import { apiGet, apiRequest } from "@/lib/api";

async function prepare(uri: string, width: number, height: number): Promise<PreparedFile> {
  const context = ImageManipulator.manipulate(uri);
  if (Math.max(width, height) > MAX_SIDE) {
    context.resize(width >= height ? { width: MAX_SIDE } : { height: MAX_SIDE });
  }
  const image = await context.renderAsync();
  // Ricodifica in JPEG: niente HEIC, peso contenuto. Il server toglie comunque ogni metadato.
  const saved = await image.saveAsync({ format: SaveFormat.JPEG, compress: 0.85 });
  const blob = await (await fetch(saved.uri)).blob();
  return { uri: saved.uri, size: blob.size, blob: Platform.OS === "web" ? blob : undefined };
}

function sendFile(
  target: NonNullable<MediaUpload["upload"]>,
  file: PreparedFile,
  onProgress: (fraction: number) => void,
  signal: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    for (const [key, value] of Object.entries(target.fields)) form.append(key, value);
    if (file.blob) {
      form.append("file", file.blob, "foto.jpg");
    } else {
      // React Native legge il file dal disco e lo invia in streaming.
      form.append("file", { uri: file.uri, name: "foto.jpg", type: "image/jpeg" } as unknown as Blob);
    }
    const xhr = new XMLHttpRequest();
    xhr.open("POST", target.url);
    xhr.timeout = 120_000;
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) onProgress(event.loaded / event.total);
    };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new UploadHttpError(xhr.status)));
    xhr.onerror = () => reject(new TypeError("Network request failed"));
    xhr.ontimeout = () => reject(new UploadHttpError(408));
    signal.addEventListener("abort", () => {
      xhr.abort();
      reject(new DOMException("Annullato", "AbortError"));
    });
    xhr.send(form);
  });
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Annullato", "AbortError"));
    });
  });
}

export function realUploadDeps(token: string): UploadDeps {
  return {
    prepare,
    createUpload: (size) =>
      apiRequest<MediaUpload>("POST", "/v1/media/uploads", {
        token,
        body: { content_type: "image/jpeg", size_bytes: size },
      }),
    completeUpload: (id) => apiRequest<MediaUpload>("POST", `/v1/media/uploads/${id}/complete`, { token }),
    getUpload: (id) => apiGet<MediaUpload>(`/v1/media/uploads/${id}`, { token }),
    sendFile,
    sleep,
  };
}

export function deleteUpload(token: string, id: string): Promise<void> {
  return apiRequest<void>("DELETE", `/v1/media/uploads/${id}`, { token }).catch(() => undefined);
}
