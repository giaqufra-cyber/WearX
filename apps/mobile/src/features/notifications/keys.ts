/** Chiavi di cache delle notifiche (in un file a parte: le usano anche follow e moderazione). */
export const NOTIFICATIONS_KEY = ["notifications"] as const;

export function notificationsKey(uid: string | undefined) {
  return [...NOTIFICATIONS_KEY, uid, "list"] as const;
}

export function unreadKey(uid: string | undefined) {
  return [...NOTIFICATIONS_KEY, uid, "unread"] as const;
}

export function settingsKey(uid: string | undefined) {
  return [...NOTIFICATIONS_KEY, uid, "settings"] as const;
}
