import AsyncStorage from "@react-native-async-storage/async-storage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PersonCard } from "@wearx/api-types";
import { render, screen, userEvent, waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import ExploreScreen from "@/app/(tabs)/explore";
import { normalizeQuery, personLine, splitMatch } from "@/features/people/format";
import { freshAvatar, pushRecent, RECENT_MAX, type RecentPerson } from "@/features/people/recent";
import { apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useLocalSearchParams: jest.fn(() => ({})),
}));
jest.mock("@/features/auth/AuthProvider", () => {
  const value = { session: { access_token: "tok", user: { id: "u1" } } };
  return { ME_QUERY_KEY: ["me"], useAuth: () => value };
});
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));

const { router, useLocalSearchParams } = jest.requireMock("expo-router") as {
  router: Record<string, jest.Mock>;
  useLocalSearchParams: jest.Mock;
};
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;

const card = (extra: Partial<PersonCard> = {}): PersonCard => ({
  nickname: "giulia.r",
  account_type: "private",
  avatar: null,
  bio: null,
  followers: 12,
  is_self: false,
  following: "none",
  follows_you: false,
  mutual_count: 0,
  mutuals: [],
  shared_style_count: 0,
  reason: null,
  ...extra,
});

// ---------- Testi ----------

test("la ricerca si scrive come i nickname", () => {
  expect(normalizeQuery("  @Giulia.R ")).toBe("giulia.r");
  expect(normalizeQuery("' or 1=1 --")).toBe("or11");
  expect(normalizeQuery("@@")).toBe("");
});

test("la riga sotto il nickname dice perché la conosci", () => {
  expect(personLine(card({ is_self: true }))).toBe("Sei tu");
  expect(personLine(card({ follows_you: true }))).toBe("Ti segue");
  expect(personLine(card({ follows_you: true, following: "pending" }))).toBe("Ti segue");
  // Se la segui già, "ti segue" non serve: si passa al motivo dopo.
  expect(personLine(card({ follows_you: true, following: "accepted" }))).toBe("12 follower");
  expect(personLine(card({ mutual_count: 1, mutuals: ["ale"] }))).toBe("Seguito da @ale");
  expect(personLine(card({ mutual_count: 2, mutuals: ["ale", "bea"] }))).toBe("Seguito da @ale e @bea");
  expect(personLine(card({ mutual_count: 5, mutuals: ["ale", "bea"] }))).toBe("Seguito da @ale, @bea e altri 3");
  expect(personLine(card({ shared_style_count: 3 }))).toBe("3 stili in comune");
  expect(personLine(card({ shared_style_count: 1 }))).toBe("1 stile in comune");
  expect(personLine(card({ account_type: "business", followers: 1200 }))).toBe("Account business · 1.200 follower");
  expect(personLine(card({ reason: "popular", followers: 1 }))).toBe("Tra i più seguiti · 1 follower");
});

test("la parte scritta si evidenzia", () => {
  expect(splitMatch("the.giulia", "giu")).toEqual(["the.", "giu", "lia"]);
  expect(splitMatch("giulia", "zzz")).toEqual(["giulia", "", ""]);
  expect(splitMatch("giulia", "")).toEqual(["giulia", "", ""]);
});

test("recenti: niente doppioni, al massimo 8, foto scadute tolte", () => {
  let list: RecentPerson[] = [];
  for (let i = 0; i < 10; i++) list = pushRecent(list, { nickname: `p${i}`, account_type: "private", avatar: null });
  expect(list).toHaveLength(RECENT_MAX);
  list = pushRecent(list, { nickname: "p5", account_type: "private", avatar: null });
  expect(list[0]!.nickname).toBe("p5");
  expect(list.filter((p) => p.nickname === "p5")).toHaveLength(1);

  const avatar = { blurhash: "x", urls: { variants: { "160": "https://x" }, expires_at: "2026-10-23T10:00:00Z" } };
  const person: RecentPerson = { nickname: "a", account_type: "private", avatar };
  expect(freshAvatar(person, Date.parse("2026-10-23T09:00:00Z"))).toBe(avatar);
  expect(freshAvatar(person, Date.parse("2026-10-23T11:00:00Z"))).toBeNull();
});

// ---------- Schermata ----------

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

let results: PersonCard[];
let suggestions: PersonCard[];

beforeEach(async () => {
  jest.clearAllMocks();
  await AsyncStorage.clear();
  useLocalSearchParams.mockReturnValue({ tab: "people" });
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });
  results = [];
  suggestions = [
    card({ nickname: "ale.fit", reason: "mutuals", mutual_count: 1, mutuals: ["bea"] }),
    card({ nickname: "negozio", account_type: "business", reason: "styles", shared_style_count: 2 }),
  ];
  get.mockImplementation((path: string) => {
    if (path === "/v1/people/suggestions") return Promise.resolve({ items: suggestions });
    if (path.startsWith("/v1/people/search?q=")) {
      const query = decodeURIComponent(path.split("q=")[1]!);
      return Promise.resolve({ query, items: results });
    }
    return Promise.reject(new Error(`inatteso: ${path}`));
  });
});
afterEach(() => client.clear());

test("suggerimenti con motivo, Segui e X", async () => {
  request.mockImplementation((method: string, path: string) =>
    Promise.resolve(path.endsWith("/follow") ? { following: "pending" } : undefined),
  );
  const user = userEvent.setup();
  await render(<ExploreScreen />, { wrapper: Providers });
  expect(screen.getByRole("radio", { name: "Persone" })).toBeChecked();
  expect(await screen.findByText("PERSONE CHE POTRESTI CONOSCERE")).toBeOnTheScreen();
  expect(await screen.findByText("Seguito da @bea")).toBeOnTheScreen();
  expect(screen.getByText("2 stili in comune")).toBeOnTheScreen();

  // Il primo "Segui" è quello di @ale.fit.
  await user.press(screen.getAllByRole("button", { name: "Segui" })[0]!);
  expect(request).toHaveBeenCalledWith("POST", "/v1/users/ale.fit/follow", { token: "tok" });
  expect(await screen.findByText("Richiesta inviata a @ale.fit.")).toBeOnTheScreen();
  expect(screen.getByRole("button", { name: "Inviata" })).toBeOnTheScreen();

  await user.press(screen.getByRole("button", { name: "Non suggerire più @negozio" }));
  expect(request).toHaveBeenCalledWith("POST", "/v1/people/suggestions/negozio/dismiss", { token: "tok" });
  await waitFor(() => expect(screen.queryByText("2 stili in comune")).toBeNull());
});

test("cerca, apri il profilo, ritrovalo nei recenti", async () => {
  results = [
    card({ nickname: "the.giulia", following: "accepted", mutual_count: 0 }),
    card({ nickname: "giulia.r", follows_you: true }),
  ];
  const user = userEvent.setup();
  await render(<ExploreScreen />, { wrapper: Providers });
  await user.type(screen.getByRole("searchbox", { name: "Cerca persone" }), "@Giu");
  expect(await screen.findByText("Ti segue")).toBeOnTheScreen();
  expect(get).toHaveBeenCalledWith("/v1/people/search?q=giu", expect.anything());
  // Già seguita: il pulsante apre il profilo invece di smettere di seguire.
  await user.press(screen.getByRole("button", { name: "Segui già" }));
  expect(router.push).toHaveBeenCalledWith({ pathname: "/user/[nickname]", params: { nickname: "the.giulia" } });
  expect(request).not.toHaveBeenCalled();

  await user.press(screen.getByRole("link", { name: "@giulia.r, Ti segue" }));
  expect(router.push).toHaveBeenLastCalledWith({ pathname: "/user/[nickname]", params: { nickname: "giulia.r" } });

  await user.press(screen.getByRole("button", { name: "Svuota la ricerca" }));
  expect(await screen.findByText("RECENTI")).toBeOnTheScreen();
  expect(screen.getByRole("link", { name: "@giulia.r, aperto di recente" })).toBeOnTheScreen();
  expect(screen.getByRole("link", { name: "@the.giulia, aperto di recente" })).toBeOnTheScreen();
  expect(JSON.parse((await AsyncStorage.getItem("wearx.recent-people.u1"))!)[0].nickname).toBe("giulia.r");

  await user.press(screen.getByRole("button", { name: "Togli @the.giulia dai recenti" }));
  expect(screen.queryByRole("link", { name: "@the.giulia, aperto di recente" })).toBeNull();
  await user.press(screen.getByRole("button", { name: "Cancella" }));
  expect(screen.queryByText("RECENTI")).toBeNull();
});

test("nessun risultato", async () => {
  const user = userEvent.setup();
  await render(<ExploreScreen />, { wrapper: Providers });
  await user.type(screen.getByRole("searchbox", { name: "Cerca persone" }), "zzz");
  expect(await screen.findByText("Nessuno con questo nickname")).toBeOnTheScreen();
});

test("la scheda Stili resta quella di prima", async () => {
  useLocalSearchParams.mockReturnValue({});
  get.mockResolvedValue({ items: [] });
  await render(<ExploreScreen />, { wrapper: Providers });
  expect(screen.getByRole("radio", { name: "Stili" })).toBeChecked();
  expect(screen.getByRole("searchbox", { name: "Cerca uno stile" })).toBeOnTheScreen();
  expect(screen.queryByRole("searchbox", { name: "Cerca persone" })).toBeNull();
});
