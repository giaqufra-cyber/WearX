import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Post } from "@wearx/api-types";
import { fireEvent, render, screen, userEvent } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { Linking } from "react-native";
import { SafeAreaProvider } from "react-native-safe-area-context";

import PostScreen from "@/app/post/[id]";
import { mapsUrl, normalizePlaceQuery, placeLabel } from "@/features/places/api";
import { PlacePicker } from "@/features/places/PlacePicker";
import { apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), navigate: jest.fn(), canGoBack: () => true },
  useLocalSearchParams: jest.fn(() => ({ id: "p1" })),
}));
let mockBand = "18_plus";
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({
    session: { access_token: "tok", user: { id: "u1" } },
    profile: { nickname: "fra.fit", age_band: mockBand },
  }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));

const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;

const scala = { name: "Teatro alla Scala", detail: "Milano, Italia", kind: "venue" as const, lat: 45.46744, lon: 9.18951 };

const post = (extra: Partial<Post> = {}): Post => ({
  id: "p1",
  status: "active",
  saved: false,
  style: { slug: "gala", name: "Galà", tone: "#3A1418" },
  author: { nickname: "fra.fit", account_type: "private" },
  is_own: true,
  archived: false,
  save_count: 0,
  caption: "Teatro",
  media: [],
  items: [],
  published_at: "2026-10-05T09:00:00Z",
  created_at: "2026-10-05T09:00:00Z",
  vote: { mine: null, my_style_confirm: null, average: null, vote_count: null, style_match: null, ask_style_confirm: false },
  ...extra,
});

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
  mockBand = "18_plus";
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });
});
afterEach(() => client.clear());

test("indirizzo per Mappe: Apple su iPhone, Google su Android e sul web", () => {
  expect(mapsUrl(scala, "ios")).toBe("https://maps.apple.com/?q=Teatro%20alla%20Scala&ll=45.46744,9.18951");
  expect(mapsUrl(scala, "android")).toBe("geo:45.46744,9.18951?q=45.46744,9.18951(Teatro%20alla%20Scala)");
  expect(mapsUrl(scala, "web")).toBe(
    "https://www.google.com/maps/search/?api=1&query=Teatro%20alla%20Scala%2C%20Milano%2C%20Italia",
  );
  expect(placeLabel(scala)).toBe("Teatro alla Scala · Milano, Italia");
  expect(normalizePlaceQuery("  teatro \n  scala ")).toBe("teatro scala");
});

test("il luogo sul fit si apre in Mappe; dal proprio fit si cambia e si toglie", async () => {
  let current = post({ place: scala });
  get.mockImplementation(async (path: string) => {
    if (path === "/v1/posts/p1") return current;
    if (path === "/v1/me/capsules") return [];
    if (path.startsWith("/v1/users/fra.fit/posts")) return { items: [], next_cursor: null, cover_id: null };
    if (path.startsWith("/v1/places")) return { items: [{ ref: "ref-brera", name: "Brera", detail: "Milano, Italia", kind: "area" }] };
    throw new Error(`percorso inatteso ${path}`);
  });
  const open = jest.spyOn(Linking, "openURL").mockResolvedValue(true);
  const u = userEvent.setup();
  await render(<PostScreen />, { wrapper: Providers });

  await u.press(await screen.findByRole("link", { name: "Luogo: Teatro alla Scala · Milano, Italia. Apri in Mappe" }));
  expect(open).toHaveBeenCalledWith(expect.stringContaining("45.46744,9.18951"));

  current = post({ place: { ...scala, name: "Brera", kind: "area", lat: 45.47206, lon: 9.18752 } });
  request.mockResolvedValue(current);
  await u.press(screen.getByRole("button", { name: "Luogo: Teatro alla Scala" }));
  await fireEvent.changeText(screen.getByRole("searchbox", { name: "Cerca il luogo" }), "brera");
  await u.press(await screen.findByRole("button", { name: "Brera, Milano, Italia" }));
  expect(request).toHaveBeenCalledWith("PATCH", "/v1/posts/p1", { token: "tok", body: { place: "ref-brera" } });
  expect(await screen.findByText("Luogo aggiunto al fit.")).toBeOnTheScreen();
  expect(screen.getByRole("button", { name: "Luogo: Brera" })).toBeOnTheScreen();

  current = post();
  request.mockResolvedValue(current);
  await u.press(screen.getByRole("button", { name: "Luogo: Brera" }));
  await u.press(screen.getByRole("button", { name: "Togli il luogo" }));
  expect(request).toHaveBeenLastCalledWith("PATCH", "/v1/posts/p1", { token: "tok", body: { place: null } });
  expect(await screen.findByRole("button", { name: "Aggiungi il luogo" })).toBeOnTheScreen();
});

test("16-17 anni: si cerca solo la città; ricerca non disponibile", async () => {
  mockBand = "16_17";
  get.mockRejectedValue(new Error("rete"));
  await render(<PlacePicker visible current={null} onClose={jest.fn()} onPick={jest.fn()} />, { wrapper: Providers });
  expect(screen.getByText(/Chi ha 16-17 anni può indicare solo la città/)).toBeOnTheScreen();
  expect(screen.queryByRole("button", { name: "Togli il luogo" })).toBeNull();
  await fireEvent.changeText(screen.getByRole("searchbox", { name: "Cerca il luogo" }), "milano");
  expect(await screen.findByText("Ricerca non disponibile ora. Riprova tra poco.")).toBeOnTheScreen();
});
