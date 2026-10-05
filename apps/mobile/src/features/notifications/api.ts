/** Notifiche: lista, contatore delle non lette, segna come lette, preferenze dei push. */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { NotificationPage, NotificationSettings, NotificationSettingsUpdate } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { NOTIFICATIONS_KEY, notificationsKey, settingsKey, unreadKey } from "@/features/notifications/keys";
import { apiGet, apiRequest } from "@/lib/api";

export { NOTIFICATIONS_KEY };

function useToken() {
  const { session } = useAuth();
  return { token: session?.access_token, uid: session?.user.id };
}

export function useNotifications() {
  const { token, uid } = useToken();
  return useInfiniteQuery({
    queryKey: notificationsKey(uid),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      apiGet<NotificationPage>(
        pageParam ? `/v1/notifications?cursor=${encodeURIComponent(pageParam)}` : "/v1/notifications",
        { token, signal },
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: Boolean(token),
    staleTime: 0,
  });
}

/** Numero sulla campanella: si aggiorna ogni minuto e quando l'app torna in primo piano. */
export function useUnreadCount() {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: unreadKey(uid),
    queryFn: ({ signal }) => apiGet<{ unread: number }>("/v1/notifications/unread", { token, signal }),
    select: (data) => data.unread,
    enabled: Boolean(token),
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}

export function useMarkAllRead() {
  const client = useQueryClient();
  const { token, uid } = useToken();
  return useMutation({
    mutationFn: () => apiRequest<void>("POST", "/v1/notifications/read", { token, body: { all: true } }),
    onMutate: () => client.setQueryData(unreadKey(uid), { unread: 0 }),
    onSettled: () => void client.invalidateQueries({ queryKey: unreadKey(uid) }),
  });
}

export function useNotificationSettings() {
  const { token, uid } = useToken();
  return useQuery({
    queryKey: settingsKey(uid),
    queryFn: ({ signal }) => apiGet<NotificationSettings>("/v1/me/notification-settings", { token, signal }),
    enabled: Boolean(token),
  });
}

export function useUpdateNotificationSettings(options: { onError?: () => void } = {}) {
  const client = useQueryClient();
  const { token, uid } = useToken();
  const key = settingsKey(uid);
  return useMutation({
    mutationFn: (patch: NotificationSettingsUpdate) =>
      apiRequest<NotificationSettings>("PATCH", "/v1/me/notification-settings", { token, body: patch }),
    onMutate: async (patch) => {
      await client.cancelQueries({ queryKey: key });
      const previous = client.getQueryData<NotificationSettings>(key);
      if (previous) client.setQueryData<NotificationSettings>(key, { ...previous, ...stripNulls(patch) });
      return { previous };
    },
    onSuccess: (saved) => client.setQueryData(key, saved),
    onError: (_error, _patch, context) => {
      client.setQueryData(key, context?.previous);
      options.onError?.();
    },
  });
}

function stripNulls(patch: NotificationSettingsUpdate): Partial<NotificationSettings> {
  return Object.fromEntries(Object.entries(patch).filter(([, v]) => v !== null && v !== undefined));
}

/** "adesso", "5 min", "3 h", "ieri", "4 g", poi la data. */
export function timeAgo(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const seconds = Math.max(0, Math.round((now.getTime() - then.getTime()) / 1000));
  if (seconds < 60) return "adesso";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "ieri";
  if (days < 7) return `${days} g`;
  return then.toLocaleDateString("it-IT", { day: "numeric", month: "short" });
}
