import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PortfolioTile, StyleCard, StyleDetail, StylePostsPage } from "@wearx/api-types";
import { act, fireEvent, render, screen, userEvent } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import ExploreScreen, { SEARCH_DEBOUNCE_MS } from "@/app/(tabs)/explore";
import FeedScreen from "@/app/(tabs)/index";
import StylePage from "@/app/style/[slug]";
import { membersLabel, seasonEndLabel, stylesCountLabel } from "@/features/styles/format";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), navigate: jest.fn(), canGoBack: () => true },
  useLocalSearchParams: jest.fn(() => ({ slug: "gala" })),
}));
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({ session: { access_token: "tok", user: { id: "u1" } } }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;

const card = (slug: string, name: string, extra: Partial<StyleCard> = {}): StyleCard => ({
  slug,
  name,
  tagline: `${name} tagline`,
  tone: "#2A2A2E",
  min_age_band: "16_17",
  category: "stili",
  seasonal: false,
  active_until: null,
  member_count: 10,
  joined: false,
  ...extra,
});

const ALL = [
  card("halloween", "Halloween", { seasonal: true, active_until: "2026-11-01", member_count: 15_100 }),
  card("old-money", "Old Money", { joined: true }),
  card("gala", "Galà"),
];

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
  // gcTime infinito: nessun timer di pulizia resta acceso a fine test (jest non uscirebbe).
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });
});
afterEach(() => client.clear());

describe("testi", () => {
  test("membri", () => {
    expect(membersLabel(0)).toBe("0 membri");
    expect(membersLabel(1)).toBe("1 membro");
    expect(membersLabel(999)).toBe("999 membri");
    expect(membersLabel(15_120)).toBe("15,1k membri");
    expect(membersLabel(2_000)).toBe("2k membri");
    expect(membersLabel(1_250_000)).toBe("1,2M membri");
  });

  test("stagione e conteggi", () => {
    expect(seasonEndLabel("2026-11-01")).toBe("FINO AL 1 NOV");
    expect(seasonEndLabel("2027-01-15")).toBe("FINO AL 15 GEN");
    expect(stylesCountLabel(1)).toBe("1 stile");
    expect(stylesCountLabel(12)).toBe("12 stili");
  });
});

describe("Esplora", () => {
  test("stile stagionale in evidenza, griglia con membri e 'Aderito', apre la pagina", async () => {
    get.mockResolvedValue({ items: ALL, total: 3 });
    const user = userEvent.setup();
    await render(<ExploreScreen />, { wrapper: Providers });

    expect(await screen.findByText("FINO AL 1 NOV")).toBeOnTheScreen();
    expect(screen.getByText("3 stili")).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: /^Old Money.*Aderito$/ })).toBeOnTheScreen();
    expect(get).toHaveBeenCalledWith("/v1/styles", expect.objectContaining({ token: "tok" }));

    await user.press(screen.getByRole("button", { name: /^Galà/ }));
    expect(router.push).toHaveBeenCalledWith({ pathname: "/style/[slug]", params: { slug: "gala" } });
  });

  test("la ricerca parte dopo la pausa di battitura, codificata; nessun risultato", async () => {
    jest.useFakeTimers();
    try {
      get.mockResolvedValueOnce({ items: ALL, total: 3 }).mockResolvedValue({ items: [], total: 0 });
      await render(<ExploreScreen />, { wrapper: Providers });
      await fireEvent.changeText(screen.getByRole("searchbox", { name: "Cerca uno stile" }), "ga");
      await fireEvent.changeText(screen.getByRole("searchbox", { name: "Cerca uno stile" }), "galà & co");
      await act(async () => {
        await jest.advanceTimersByTimeAsync(SEARCH_DEBOUNCE_MS);
      });
      await act(async () => {
        await jest.advanceTimersByTimeAsync(50);
      });
      const paths = get.mock.calls.map((c) => c[0]);
      expect(paths).toEqual(["/v1/styles", "/v1/styles?q=gal%C3%A0%20%26%20co"]);
      expect(screen.getByText("Nessuno stile trovato")).toBeOnTheScreen();
      expect(screen.getByText("RISULTATI")).toBeOnTheScreen();
    } finally {
      jest.useRealTimers();
    }
  });

  test("errore di rete con Riprova", async () => {
    get.mockRejectedValueOnce(new TypeError("Network request failed")).mockResolvedValue({ items: ALL, total: 3 });
    const user = userEvent.setup();
    await render(<ExploreScreen />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("3 stili")).toBeOnTheScreen();
  });
});

describe("Pagina dello stile", () => {
  const detail = (extra: Partial<StyleDetail> = {}): StyleDetail => ({
    ...card("gala", "Galà", { member_count: 41 }),
    posts_last_7_days: 0,
    ...extra,
  });

  const tile = (id: string, caption: string | null, extra: Partial<PortfolioTile> = {}): PortfolioTile => ({
    id,
    status: "active",
    style: { slug: "gala", name: "Galà", tone: "#3A1418" },
    caption,
    capsule_id: null,
    media_count: 1,
    photo: null,
    mine: null,
    average: null,
    vote_count: 0,
    own: false,
    ...extra,
  });
  /** Dettaglio dello stile e griglia dei fit (una pagina per ordine). */
  const serve = (value: StyleDetail, pages: Partial<Record<"top" | "new", StylePostsPage>> = {}) =>
    get.mockImplementation((path: string) => {
      if (!path.includes("/posts?")) return Promise.resolve(value);
      const sort = new URLSearchParams(path.split("?")[1]).get("sort") as "top" | "new";
      return Promise.resolve(pages[sort] ?? { items: [], next_cursor: null });
    });

  test("griglia dei fit: in evidenza o recenti, i propri con il proprio stato", async () => {
    serve(detail({ posts_last_7_days: 2 }), {
      top: { items: [tile("p1", "Teatro", { average: 91, vote_count: 40 }), tile("p2", null)], next_cursor: null },
      new: { items: [tile("p3", "Il mio", { own: true })], next_cursor: null },
    });
    const user = userEvent.setup();
    await render(<StylePage />, { wrapper: Providers });
    expect(await screen.findByRole("button", { name: "Fit, Galà, Teatro, media 91" })).toBeOnTheScreen();
    // Senza didascalia non ripete il nome dello stile come titolo.
    expect(screen.getByRole("button", { name: "Fit, Galà" })).toBeOnTheScreen();
    expect(get).toHaveBeenCalledWith("/v1/styles/gala/posts?sort=top&limit=24", expect.objectContaining({ token: "tok" }));

    await user.press(screen.getByRole("radio", { name: "Recenti" }));
    await user.press(await screen.findByRole("button", { name: /^Fit, Galà, Il mio/ }));
    expect(router.push).toHaveBeenCalledWith(expect.stringContaining("p3"));
  });

  test("stile senza fit: invito a pubblicare", async () => {
    serve(detail());
    const user = userEvent.setup();
    await render(<StylePage />, { wrapper: Providers });
    expect(await screen.findByText("Ancora nessun fit in questo stile")).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Pubblica un fit" }));
    expect(router.push).toHaveBeenCalledWith("/new-post");
  });

  test("Entra: si vede subito, poi conferma del server", async () => {
    serve(detail());
    let resolve: (value: StyleCard) => void = () => undefined;
    request.mockReturnValue(new Promise<StyleCard>((r) => (resolve = r)));
    const user = userEvent.setup();
    await render(<StylePage />, { wrapper: Providers });

    expect(await screen.findByText("STILE · 41 MEMBRI")).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Entra in Galà" }));
    // Prima ancora della risposta: già dentro, un membro in più.
    expect(screen.getByText("Sei dentro")).toBeOnTheScreen();
    expect(screen.getByText("STILE · 42 MEMBRI")).toBeOnTheScreen();
    expect(request).toHaveBeenCalledWith("PUT", "/v1/styles/gala/membership", { token: "tok" });

    serve(detail({ joined: true, member_count: 42 }));
    await act(async () => resolve({ ...card("gala", "Galà"), joined: true, member_count: 42 }));
    expect(screen.getByText("Sei entrato in Galà. Lo trovi nel feed.")).toBeOnTheScreen();
  });

  test("ultimo stile: il server rifiuta, si torna come prima con il messaggio", async () => {
    serve(detail({ joined: true, member_count: 5 }));
    request.mockRejectedValue(new ApiError(409, "style.last_membership", "Ultimo"));
    const user = userEvent.setup();
    await render(<StylePage />, { wrapper: Providers });

    await user.press(await screen.findByRole("button", { name: /Sei dentro Galà/ }));
    expect(request).toHaveBeenCalledWith("DELETE", "/v1/styles/gala/membership", { token: "tok" });
    expect(await screen.findByText("Resta almeno in uno stile: il tuo feed è fatto di questi.")).toBeOnTheScreen();
    expect(screen.getByText("Sei dentro")).toBeOnTheScreen();
    expect(screen.getByText("STILE · 5 MEMBRI")).toBeOnTheScreen();
  });

  test("stile non disponibile (fuori stagione o 18+)", async () => {
    get.mockRejectedValue(new ApiError(404, "style.not_found", "Non trovato"));
    await render(<StylePage />, { wrapper: Providers });
    expect(await screen.findByText("Stile non disponibile")).toBeOnTheScreen();
  });

  test("stagionale: mostra la fine della stagione", async () => {
    serve(detail({ seasonal: true, active_until: "2026-11-01", posts_last_7_days: 1 }));
    await render(<StylePage />, { wrapper: Providers });
    expect(await screen.findByText("STAGIONALE · FINO AL 1 NOV")).toBeOnTheScreen();
    expect(screen.getByText("1 FIT QUESTA SETTIMANA")).toBeOnTheScreen();
  });
});

describe("Feed", () => {
  test("le chip sono i tuoi stili, più la scorciatoia per aggiungerne", async () => {
    const mine = { items: [card("old-money", "Old Money", { joined: true }), card("gala", "Galà")], total: 2 };
    get.mockImplementation((path: string) =>
      Promise.resolve(path.startsWith("/v1/feed") ? { items: [], next_cursor: null, empty_reason: "no_posts" } : mine),
    );
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });
    expect(await screen.findByRole("tab", { name: "Old Money" })).toBeOnTheScreen();
    expect(screen.queryByText("Halloween")).toBeNull();
    expect(get).toHaveBeenCalledWith("/v1/me/styles", expect.objectContaining({ token: "tok" }));

    await user.press(screen.getByRole("tab", { name: "Galà" }));
    expect(screen.getByRole("tab", { name: "Galà" })).toBeSelected();
    await user.press(screen.getByRole("button", { name: "Aggiungi stili" }));
    expect(router.navigate).toHaveBeenCalledWith("/explore");
  });
});
