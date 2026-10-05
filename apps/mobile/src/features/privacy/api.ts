/** Privacy e sicurezza: profilo, dispositivi, archivio dei dati, cancellazione dell'account. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  DataExport,
  DeletionScheduled,
  DeletionStatus,
  Device,
  Profile,
  ProfileUpdate,
} from "@wearx/api-types";
import * as Device_ from "expo-device";
import { Platform } from "react-native";

import { ME_QUERY_KEY, useAuth } from "@/features/auth/AuthProvider";
import { timeAgo } from "@/features/notifications/api";
import { APP_VERSION, apiGet, apiRequest } from "@/lib/api";

export const PRIVACY_KEY = ["privacy"] as const;

function useToken() {
  const { session } = useAuth();
  return { token: session?.access_token, uid: session?.user.id };
}

/** Impostazioni del profilo (nascondi prezzi, nascondi numero dei voti), subito a schermo. */
export function useUpdateProfile(options: { onError?: () => void } = {}) {
  const client = useQueryClient();
  const { token, uid } = useToken();
  const key = [...ME_QUERY_KEY, uid];
  return useMutation({
    mutationFn: (patch: ProfileUpdate) => apiRequest<Profile>("PATCH", "/v1/me", { token, body: patch }),
    onMutate: async (patch) => {
      await client.cancelQueries({ queryKey: key });
      const previous = client.getQueryData<Profile>(key);
      if (previous) client.setQueryData<Profile>(key, { ...previous, ...(patch as Partial<Profile>) });
      return { previous };
    },
    onSuccess: (saved) => client.setQueryData(key, saved),
    onError: (_error, _patch, context) => {
      client.setQueryData(key, context?.previous);
      options.onError?.();
    },
  });
}

/** Nome del dispositivo come lo mostra la lista ("iPhone 15", "Pixel 8", "Browser web"). */
export function deviceLabel(): string {
  if (Platform.OS === "web") return "Browser web";
  return Device_.modelName ?? (Platform.OS === "ios" ? "iPhone" : "Telefono Android");
}

/** "Sono qui": all'avvio e quando l'app torna in primo piano. */
export async function pingDevice(token: string): Promise<void> {
  await apiRequest("PUT", "/v1/me/devices/current", {
    token,
    body: {
      label: deviceLabel(),
      platform: Platform.OS === "ios" ? "ios" : Platform.OS === "android" ? "android" : "web",
      app_version: APP_VERSION,
    },
  });
}

export function useDevices() {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: [...PRIVACY_KEY, uid, "devices"],
    queryFn: ({ signal }) => apiGet<Device[]>("/v1/me/devices", { token, signal }),
    enabled: Boolean(token),
  });
}

export function useRevokeDevice() {
  const client = useQueryClient();
  const { token, uid } = useToken();
  return useMutation({
    mutationFn: (id: string) => apiRequest<void>("DELETE", `/v1/me/devices/${encodeURIComponent(id)}`, { token }),
    onSettled: () => void client.invalidateQueries({ queryKey: [...PRIVACY_KEY, uid, "devices"] }),
  });
}

export function useExport() {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: [...PRIVACY_KEY, uid, "export"],
    queryFn: ({ signal }) => apiGet<DataExport | null>("/v1/me/export", { token, signal }),
    enabled: Boolean(token),
    // Mentre si prepara, si ricontrolla ogni 5 secondi.
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 5000 : false),
  });
}

export function useRequestExport() {
  const client = useQueryClient();
  const { token, uid } = useToken();
  return useMutation({
    mutationFn: () => apiRequest<DataExport>("POST", "/v1/me/export", { token }),
    onSuccess: (created) => client.setQueryData([...PRIVACY_KEY, uid, "export"], created),
  });
}

export function useDeletionStatus() {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: [...PRIVACY_KEY, uid, "deletion"],
    queryFn: ({ signal }) => apiGet<DeletionStatus>("/v1/me/deletion", { token, signal }),
    enabled: Boolean(token),
  });
}

/** Dopo la richiesta o l'annullamento si rilegge il profilo: è lui che decide la schermata. */
export function useDeletion() {
  const client = useQueryClient();
  const { token } = useToken();
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ME_QUERY_KEY });
    void client.invalidateQueries({ queryKey: PRIVACY_KEY });
  };
  const request = useMutation({
    mutationFn: (nickname: string) =>
      apiRequest<DeletionScheduled>("POST", "/v1/me/deletion", { token, body: { nickname } }),
    onSuccess: refresh,
  });
  const cancel = useMutation({
    mutationFn: () => apiRequest<void>("DELETE", "/v1/me/deletion", { token }),
    onSuccess: refresh,
  });
  return { request, cancel };
}

/** 2_400_000 byte -> "2,3 MB". */
export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

export function longDate(iso: string): string {
  return new Date(iso).toLocaleDateString("it-IT", { day: "numeric", month: "long", year: "numeric" });
}

/** "attivo adesso", "attivo 5 min fa", "attivo ieri", "attivo il 3 set". */
export function lastSeen(iso: string, now: Date = new Date()): string {
  const ago = timeAgo(iso, now);
  if (ago === "adesso" || ago === "ieri") return `attivo ${ago}`;
  if (/^\d+ (min|h|g)$/.test(ago)) return `attivo ${ago} fa`;
  return `attivo il ${ago}`;
}

