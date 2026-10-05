/**
 * Push sul telefono (expo-notifications). Il permesso si chiede solo quando la persona tocca
 * "Attiva" (mai all'avvio). Sul web e nei simulatori i push non esistono: tutto resta nella
 * lista dentro l'app.
 */
import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

import { apiRequest } from "@/lib/api";

export type PushStatus = "granted" | "denied" | "undetermined" | "unsupported";

let registeredToken: string | null = null;
let handlerSet = false;

export function pushSupported(): boolean {
  return Platform.OS !== "web" && Device.isDevice;
}

/** Come mostrare un push che arriva con l'app aperta: in alto, senza suono. */
export function setForegroundHandler(): void {
  if (handlerSet || Platform.OS === "web") return;
  handlerSet = true;
  Notifications.setNotificationHandler({
    handleNotification: async () => ({
      shouldShowBanner: true,
      shouldShowList: true,
      shouldPlaySound: false,
      shouldSetBadge: true,
    }),
  });
}

export async function pushStatus(): Promise<PushStatus> {
  if (!pushSupported()) return "unsupported";
  const current = await Notifications.getPermissionsAsync();
  if (current.granted) return "granted";
  return current.canAskAgain ? "undetermined" : "denied";
}

function projectId(): string | undefined {
  const extra = Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined;
  return extra?.eas?.projectId ?? Constants.easConfig?.projectId;
}

/**
 * Registra questo telefono per i push. Con `ask` chiede il permesso se non è ancora stato
 * deciso; senza, registra solo se il permesso c'è già (es. all'avvio, per rinnovare il token).
 */
export async function enablePush(token: string, { ask }: { ask: boolean }): Promise<PushStatus> {
  if (!pushSupported()) return "unsupported";
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("default", {
      name: "Notifiche",
      importance: Notifications.AndroidImportance.DEFAULT,
    });
  }
  let status = await pushStatus();
  if (status === "undetermined" && ask) {
    const answer = await Notifications.requestPermissionsAsync();
    status = answer.granted ? "granted" : answer.canAskAgain ? "undetermined" : "denied";
  }
  if (status !== "granted") return status;
  const id = projectId();
  // Senza progetto EAS (arriva con la seduta 23) Expo non rilascia token: si riprova al prossimo avvio.
  if (!id) return status;
  const { data } = await Notifications.getExpoPushTokenAsync({ projectId: id });
  await apiRequest<void>("PUT", "/v1/me/push-tokens", {
    token,
    body: { token: data, platform: Platform.OS === "ios" ? "ios" : "android" },
  });
  registeredToken = data;
  return status;
}

/** All'uscita dall'account: questo telefono smette di ricevere i push di quell'account. */
export async function forgetThisDevice(token: string | undefined): Promise<void> {
  const device = registeredToken;
  registeredToken = null;
  if (!device || !token) return;
  try {
    await apiRequest<void>("DELETE", `/v1/me/push-tokens/${encodeURIComponent(device)}`, { token });
  } catch {
    // Offline: il token scade comunque quando Expo segnala che non è più valido.
  }
  if (Platform.OS !== "web") await Notifications.setBadgeCountAsync(0);
}

const SAFE_ROUTE = /^\/(notifications|moderation|data-export|post\/[A-Za-z0-9-]{1,64}|user\/[A-Za-z0-9._]{3,20})$/;

/** Solo percorsi interni noti: un push non deve poter aprire un indirizzo qualsiasi. */
export function safeRoute(url: unknown): string | null {
  return typeof url === "string" && SAFE_ROUTE.test(url) ? url : null;
}
