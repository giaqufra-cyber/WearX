import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AppNotification, NotificationPage } from "@wearx/api-types";
import { act, render, screen, userEvent, waitFor } from "@testing-library/react-native";
import * as Notifications from "expo-notifications";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import NotificationSettingsScreen from "@/app/notification-settings";
import { AppBridges } from "@/features/notifications/AppBridges";
import { timeAgo } from "@/features/notifications/api";
import { NotificationBell } from "@/features/notifications/NotificationBell";
import { NotificationList } from "@/features/notifications/NotificationList";
import { enablePush, forgetThisDevice, safeRoute } from "@/features/notifications/push";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { configureEvents, flushEvents, pendingEvents, resetEvents, track } from "@/lib/events";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), navigate: jest.fn(), canGoBack: () => true },
}));
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({ session: { access_token: "tok", user: { id: "u1" } }, profile: { nickname: "fra.fit" } }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));
jest.mock("expo-device", () => ({ isDevice: true }));
jest.mock("expo-constants", () => ({
  __esModule: true,
  default: { expoConfig: { version: "0.1.0", extra: { eas: { projectId: "proj-1" } } } },
}));
let mockResponseListener: ((r: unknown) => void) | null = null;
jest.mock("expo-notifications", () => ({
  AndroidImportance: { DEFAULT: 3 },
  setNotificationHandler: jest.fn(),
  setNotificationChannelAsync: jest.fn(),
  getPermissionsAsync: jest.fn(),
  requestPermissionsAsync: jest.fn(),
  getExpoPushTokenAsync: jest.fn(),
  setBadgeCountAsync: jest.fn(() => Promise.resolve(true)),
  addNotificationReceivedListener: jest.fn(() => ({ remove: jest.fn() })),
  addNotificationResponseReceivedListener: jest.fn((fn: (r: unknown) => void) => {
    mockResponseListener = fn;
    return { remove: jest.fn() };
  }),
  getLastNotificationResponse: jest.fn(() => null),
  clearLastNotificationResponse: jest.fn(),
}));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;
const perms = Notifications.getPermissionsAsync as jest.Mock;
const ask = Notifications.requestPermissionsAsync as jest.Mock;
const pushToken = Notifications.getExpoPushTokenAsync as jest.Mock;

const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 47, left: 0, right: 0, bottom: 34 } };
let client: QueryClient;
function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <SafeAreaProvider initialMetrics={metrics}>
        <ToastProvider>{children}</ToastProvider>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });
  perms.mockResolvedValue({ granted: true, canAskAgain: true });
  request.mockResolvedValue(undefined);
});
afterEach(() => client.clear());

const notification = (extra: Partial<AppNotification> = {}): AppNotification => ({
  id: "n1",
  type: "new_follower",
  title: "@giulia.rossi ha iniziato a seguirti",
  body: "",
  url: "/user/giulia.rossi",
  created_at: new Date(Date.now() - 5 * 60_000).toISOString(),
  read: false,
  actor: { nickname: "giulia.rossi", account_type: "private", can_open: true },
  post: null,
  ...extra,
});

const page = (items: AppNotification[], unread = items.filter((i) => !i.read).length): NotificationPage => ({
  items,
  next_cursor: null,
  unread,
});

describe("Formati", () => {
  test("tempo trascorso", () => {
    const now = new Date("2026-10-05T12:00:00Z");
    expect(timeAgo("2026-10-05T11:59:30Z", now)).toBe("adesso");
    expect(timeAgo("2026-10-05T11:55:00Z", now)).toBe("5 min");
    expect(timeAgo("2026-10-05T09:00:00Z", now)).toBe("3 h");
    expect(timeAgo("2026-10-04T10:00:00Z", now)).toBe("ieri");
    expect(timeAgo("2026-10-01T10:00:00Z", now)).toBe("4 g");
    expect(timeAgo("2026-09-01T10:00:00Z", now)).toMatch(/1 set/);
  });

  test("un push apre solo percorsi interni noti", () => {
    expect(safeRoute("/post/9f1c-22")).toBe("/post/9f1c-22");
    expect(safeRoute("/user/giulia.rossi")).toBe("/user/giulia.rossi");
    expect(safeRoute("/moderation")).toBe("/moderation");
    for (const bad of ["https://evil.example", "//evil.example", "/user/../admin", "/new-post", 42, null, "/post/"]) {
      expect(safeRoute(bad)).toBeNull();
    }
  });
});

describe("Lista delle notifiche", () => {
  test("righe, pallino delle nuove, tutto letto all'apertura, tocco", async () => {
    get.mockResolvedValue(
      page([
        notification(),
        notification({
          id: "n2",
          type: "vote_milestone",
          title: "Il tuo fit «Serata» ha raggiunto 50 voti",
          url: "/post/p1",
          actor: null,
          read: true,
          created_at: "2026-09-01T10:00:00Z",
        }),
      ]),
    );
    const user = userEvent.setup();
    await render(<NotificationList />, { wrapper: Providers });
    const fresh = await screen.findByRole("button", { name: /^Nuova\. @giulia\.rossi ha iniziato a seguirti/ });
    expect(screen.getByText("5 MIN")).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: /^Il tuo fit «Serata» ha raggiunto 50 voti/ })).toBeOnTheScreen();
    expect(request).toHaveBeenCalledWith("POST", "/v1/notifications/read", { token: "tok", body: { all: true } });
    await user.press(fresh);
    expect(router.push).toHaveBeenCalledWith("/user/giulia.rossi");
  });

  test("richiesta di follow: accetta dalla lista", async () => {
    get.mockResolvedValue(
      page([notification({ type: "follow_request", title: "@giulia.rossi vuole seguirti", url: "/notifications" })]),
    );
    const user = userEvent.setup();
    await render(<NotificationList />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Accetta" }));
    expect(request).toHaveBeenCalledWith("POST", "/v1/me/follow-requests", {
      token: "tok",
      body: { nickname: "giulia.rossi", decision: "accept" },
    });
    expect(router.push).not.toHaveBeenCalled(); // il pulsante non apre anche il profilo
  });

  test("vuota", async () => {
    get.mockResolvedValue(page([]));
    perms.mockResolvedValue({ granted: true, canAskAgain: true });
    await render(<NotificationList />, { wrapper: Providers });
    expect(await screen.findByText("Nessuna notifica")).toBeOnTheScreen();
    expect(request).not.toHaveBeenCalledWith("POST", "/v1/notifications/read", expect.anything());
  });

  test("invito ad attivare i push: permesso chiesto solo al tocco, token registrato", async () => {
    get.mockResolvedValue(page([]));
    perms.mockResolvedValue({ granted: false, canAskAgain: true });
    ask.mockResolvedValue({ granted: true, canAskAgain: true });
    pushToken.mockResolvedValue({ data: "ExponentPushToken[abcdefghij123]" });
    const user = userEvent.setup();
    await render(<NotificationList />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Attiva" }));
    expect(ask).toHaveBeenCalledTimes(1);
    expect(pushToken).toHaveBeenCalledWith({ projectId: "proj-1" });
    expect(request).toHaveBeenCalledWith("PUT", "/v1/me/push-tokens", {
      token: "tok",
      body: { token: "ExponentPushToken[abcdefghij123]", platform: "ios" },
    });
  });

  test("permesso negato: si spiega come riattivarlo", async () => {
    get.mockResolvedValue(page([]));
    perms.mockResolvedValue({ granted: false, canAskAgain: false });
    await render(<NotificationList />, { wrapper: Providers });
    expect(await screen.findByText("Notifiche spente sul telefono")).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Apri impostazioni" })).toBeOnTheScreen();
  });
});

describe("Campanella e impostazioni", () => {
  test("numero delle non lette", async () => {
    get.mockResolvedValue({ unread: 3 });
    const user = userEvent.setup();
    const { rerender } = await render(<NotificationBell />, { wrapper: Providers });
    const bell = await screen.findByRole("button", { name: "Notifiche, 3 non lette" });
    expect(screen.getByText("3")).toBeOnTheScreen();
    await user.press(bell);
    expect(router.push).toHaveBeenCalledWith("/notifications");
    client.setQueryData(["notifications", "u1", "unread"], { unread: 140 });
    await rerender(<NotificationBell />);
    expect(screen.getByText("99+")).toBeOnTheScreen();
  });

  test("interruttori dei push", async () => {
    get.mockResolvedValue({ follows: true, votes: true, moderation: true });
    request.mockResolvedValue({ follows: true, votes: false, moderation: true });
    const user = userEvent.setup();
    await render(<NotificationSettingsScreen />, { wrapper: Providers });
    const votes = await screen.findByRole("switch", { name: "Voti ai tuoi fit" });
    expect(votes).toBeChecked();
    await user.press(votes);
    expect(request).toHaveBeenCalledWith("PATCH", "/v1/me/notification-settings", { token: "tok", body: { votes: false } });
    expect(await screen.findByRole("switch", { name: "Voti ai tuoi fit" })).not.toBeChecked();
    expect(screen.getByText(/tra le 22 e le 7/)).toBeOnTheScreen();
  });
});

describe("Push sul telefono", () => {
  test("tocco su un push: solo percorsi sicuri", async () => {
    get.mockResolvedValue({ unread: 2 });
    await render(<AppBridges />, { wrapper: Providers });
    expect(Notifications.setNotificationHandler).toHaveBeenCalled();
    const tap = (url: unknown) =>
      act(() => mockResponseListener?.({ notification: { request: { content: { data: { url } } } } }));
    await tap("/post/p1");
    expect(router.push).toHaveBeenCalledWith("/post/p1");
    router.push!.mockClear();
    await tap("https://evil.example");
    expect(router.push).not.toHaveBeenCalled();
    await waitFor(() => expect(Notifications.setBadgeCountAsync).toHaveBeenCalledWith(2));
  });

  test("all'avvio con permesso già dato il token si rinnova; all'uscita si cancella", async () => {
    pushToken.mockResolvedValue({ data: "ExponentPushToken[zzzzzzzzzz999]" });
    expect(await enablePush("tok", { ask: false })).toBe("granted");
    expect(ask).not.toHaveBeenCalled();
    await forgetThisDevice("tok");
    expect(request).toHaveBeenCalledWith("DELETE", `/v1/me/push-tokens/${encodeURIComponent("ExponentPushToken[zzzzzzzzzz999]")}`, {
      token: "tok",
    });
    request.mockClear();
    await forgetThisDevice("tok"); // già fatto: niente
    expect(request).not.toHaveBeenCalled();
  });

  test("senza permesso e senza chiedere: niente token", async () => {
    perms.mockResolvedValue({ granted: false, canAskAgain: true });
    expect(await enablePush("tok", { ask: false })).toBe("undetermined");
    expect(pushToken).not.toHaveBeenCalled();
  });
});

describe("Eventi d'uso", () => {
  beforeEach(() => {
    resetEvents();
    configureEvents(() => "tok");
  });

  test("una volta per sessione, a gruppi da 50", async () => {
    track({ name: "post_impression", post_id: "p1", source: "feed" });
    track({ name: "post_impression", post_id: "p1", source: "feed" });
    track({ name: "profile_view", nickname: "Giulia.Rossi" });
    track({ name: "profile_view", nickname: "giulia.rossi" });
    track({ name: "shop_click", post_id: "p1", item: 0 });
    track({ name: "shop_click", post_id: "p1", item: 0 }); // i tocchi contano tutti
    expect(pendingEvents().map((e) => e.name)).toEqual(["post_impression", "profile_view", "shop_click", "shop_click"]);
    expect(pendingEvents()[0]!.at).toMatch(/^\d{4}-/);

    for (let i = 0; i < 60; i++) track({ name: "post_open", post_id: `x${i}`, source: "profile" });
    await flushEvents();
    const sizes = request.mock.calls.map(([, , o]) => (o as { body: { events: unknown[] } }).body.events.length);
    expect(sizes.reduce((a, b) => a + b, 0)).toBe(64);
    expect(Math.max(...sizes)).toBeLessThanOrEqual(50);
    expect(pendingEvents()).toHaveLength(0);
  });

  test("senza rete si riprova; gruppo rifiutato si scarta", async () => {
    request.mockRejectedValueOnce(new TypeError("Network request failed"));
    track({ name: "shop_click", post_id: "p1", item: 1 });
    await flushEvents();
    expect(pendingEvents()).toHaveLength(1);
    request.mockRejectedValueOnce(new ApiError(422, "validation", "no"));
    await flushEvents();
    expect(pendingEvents()).toHaveLength(0);
  });

  test("senza accesso non parte nulla", async () => {
    configureEvents(() => undefined);
    track({ name: "shop_click", post_id: "p1", item: 1 });
    await flushEvents();
    expect(request).not.toHaveBeenCalled();
  });
});
