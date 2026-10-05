/**
 * Collegamenti attivi solo dentro l'app (dopo l'accesso):
 * - push: rinnova il token se il permesso c'è già, apre la schermata giusta al tocco di un push,
 *   aggiorna lista e campanella quando ne arriva uno con l'app aperta, tiene il numero sull'icona;
 * - eventi d'uso: li spedisce a gruppi, e subito quando l'app va in background.
 */
import { useQueryClient } from "@tanstack/react-query";
import * as Notifications from "expo-notifications";
import { router } from "expo-router";
import { useEffect, useRef } from "react";
import { AppState, Platform } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { useUnreadCount } from "@/features/notifications/api";
import { NOTIFICATIONS_KEY } from "@/features/notifications/keys";
import { enablePush, safeRoute, setForegroundHandler } from "@/features/notifications/push";
import { configureEvents, FLUSH_EVERY_MS, flushEvents, resetEvents } from "@/lib/events";

export function AppBridges() {
  const { session } = useAuth();
  const token = session?.access_token;
  const uid = session?.user.id;
  const client = useQueryClient();
  const unread = useUnreadCount();

  // Eventi: sempre con il token corrente; nuova persona = nuova sessione di conteggio.
  const tokenRef = useRef(token);
  tokenRef.current = token;
  useEffect(() => {
    configureEvents(() => tokenRef.current);
    resetEvents();
    const timer = setInterval(() => void flushEvents(), FLUSH_EVERY_MS);
    const sub = AppState.addEventListener("change", (state) => {
      if (state !== "active") void flushEvents();
    });
    return () => {
      clearInterval(timer);
      sub.remove();
      void flushEvents();
    };
  }, [uid]);

  // Push: solo telefoni veri. Il permesso NON si chiede qui.
  useEffect(() => {
    if (Platform.OS === "web" || !token) return;
    setForegroundHandler();
    void enablePush(token, { ask: false }).catch(() => undefined);
  }, [uid]);

  useEffect(() => {
    if (Platform.OS === "web") return;
    const received = Notifications.addNotificationReceivedListener(() => {
      void client.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
    });
    const tapped = Notifications.addNotificationResponseReceivedListener((response) => {
      const target = safeRoute(response.notification.request.content.data?.url);
      void client.invalidateQueries({ queryKey: NOTIFICATIONS_KEY });
      if (target) router.push(target as never);
    });
    // App aperta toccando un push mentre era chiusa.
    const last = Notifications.getLastNotificationResponse();
    const initial = safeRoute(last?.notification.request.content.data?.url);
    if (initial) {
      router.push(initial as never);
      Notifications.clearLastNotificationResponse();
    }
    return () => {
      received.remove();
      tapped.remove();
    };
  }, [client]);

  // Numero sull'icona dell'app = notifiche non lette.
  useEffect(() => {
    if (Platform.OS === "web" || unread.data === undefined) return;
    void Notifications.setBadgeCountAsync(unread.data).catch(() => undefined);
  }, [unread.data]);

  return null;
}
