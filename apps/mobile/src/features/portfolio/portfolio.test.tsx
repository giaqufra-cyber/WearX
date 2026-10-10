import type { InfiniteData } from "@tanstack/react-query";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Capsule, PortfolioPage, PortfolioTile, Post, UserProfile } from "@wearx/api-types";
import { act, render, screen, userEvent } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import PostScreen from "@/app/post/[id]";
import { afterIdForStep, moveId, reorderPages } from "@/features/portfolio/api";
import { accountTypeLabel, positionLabel, tileScore, tileStatus } from "@/features/portfolio/format";
import { CAPSULE_SIZES, capsuleWidth, shelfHeight } from "@/features/portfolio/CapsuleShelf";
import { PortfolioScreen } from "@/features/portfolio/PortfolioScreen";
import { compactNumber } from "@/features/styles/format";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), navigate: jest.fn(), canGoBack: () => true },
  useLocalSearchParams: jest.fn(() => ({ id: "p2" })),
}));
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({
    session: { access_token: "tok", user: { id: "u1" } },
    profile: { nickname: "fra.fit" },
    signOut: jest.fn(),
  }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;

const tile = (id: string, caption: string, extra: Partial<PortfolioTile> = {}): PortfolioTile => ({
  id,
  status: "active",
  style: { slug: "gala", name: "Galà", tone: "#3A1418" },
  caption,
  capsule_id: null,
  media_count: 1,
  photo: null,
  mine: null,
  average: 90,
  vote_count: 1120,
  own: false,
  ...extra,
});

const TILES = [tile("p1", "Capodanno"), tile("p2", "Teatro"), tile("p3", "Ufficio")];
const page = (items: PortfolioTile[], extra: Partial<PortfolioPage> = {}): PortfolioPage => ({
  items,
  next_cursor: null,
  cover_id: items[0]?.id ?? null,
  ...extra,
});

const user = (extra: Partial<UserProfile> = {}): UserProfile => ({
  verified_domains: [],
  nickname: "fra.fit",
  bio: "Trento, presto Monaco.",
  account_type: "private",
  is_self: true,
  can_view_posts: true,
  styles: [{ slug: "gala", name: "Galà", tone: "#3A1418" }],
  stats: { posts: 3, average: 88.4, votes: 5120 },
  capsules: [{ id: "c1", name: "Serate", post_count: 1 }],
  followers: 12,
  following: 30,
  relationship: { following: "none", follows_you: false },
  pending_requests: 0,
  ...extra,
});

const CAPSULES: Capsule[] = [
  { id: "c1", name: "Serate", post_count: 1 },
  { id: "c2", name: "Ufficio", post_count: 0 },
];

function serve(profile: UserProfile | Error, grid: PortfolioPage | ((path: string) => PortfolioPage) = page(TILES)) {
  get.mockImplementation((path: string) => {
    if (path === "/v1/users/fra.fit" || path === "/v1/users/altro") {
      return profile instanceof Error ? Promise.reject(profile) : Promise.resolve(profile);
    }
    if (path.startsWith("/v1/users/")) return Promise.resolve(typeof grid === "function" ? grid(path) : grid);
    if (path === "/v1/me/capsules") return Promise.resolve(CAPSULES);
    return Promise.reject(new Error(`percorso inatteso ${path}`));
  });
}

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
});
afterEach(() => client.clear());

describe("ordine e testi", () => {
  test("spostare un fit nell'elenco", () => {
    const ids = ["a", "b", "c", "d"];
    expect(moveId(ids, "c", null)).toEqual(["c", "a", "b", "d"]);
    expect(moveId(ids, "a", "c")).toEqual(["b", "c", "a", "d"]);
    expect(moveId(ids, "d", "a")).toEqual(["a", "d", "b", "c"]);
    expect(moveId(ids, "b", "zzz")).toEqual(ids);
  });

  test("frecce: chi deve precedere il fit", () => {
    const ids = ["a", "b", "c", "d"];
    expect(afterIdForStep(ids, 1, -1)).toBeNull(); // b in testa
    expect(afterIdForStep(ids, 2, -1)).toBe("a"); // c prima di b
    expect(afterIdForStep(ids, 1, 1)).toBe("c"); // b dopo c
    expect(afterIdForStep(ids, 0, -1)).toBeUndefined();
    expect(afterIdForStep(ids, 3, 1)).toBeUndefined();
  });

  test("le pagine in cache mantengono la loro lunghezza e la copertina segue", () => {
    const data: InfiniteData<PortfolioPage> = {
      pageParams: [null, "x"],
      pages: [page(TILES.slice(0, 2), { next_cursor: "x" }), page(TILES.slice(2), { cover_id: "p1" })],
    };
    const moved = reorderPages(data, "p3", null);
    expect(moved.pages.map((p) => p.items.map((t) => t.id))).toEqual([["p3", "p1"], ["p2"]]);
    expect(moved.pages.map((p) => p.cover_id)).toEqual(["p3", "p3"]);
    expect(moved.pages[0]!.next_cursor).toBe("x");
  });

  test("numeri, etichette, voti dei tile", () => {
    expect(positionLabel(0)).toBe("01");
    expect(positionLabel(11)).toBe("12");
    expect(compactNumber(950)).toBe("950");
    expect(compactNumber(1120)).toBe("1,1k");
    expect(compactNumber(2_000_000)).toBe("2M");
    expect(accountTypeLabel("business")).toBe("BUSINESS");
    expect(accountTypeLabel("private")).toBe("PRIVATO");
    expect(tileScore(tile("a", "x", { average: 91.4, vote_count: 1 }), false)).toEqual({ score: "91", sub: "1 voto" });
    expect(tileScore(tile("a", "x", { average: 80, vote_count: null }), false)).toEqual({ score: "80", sub: "media" });
    expect(tileScore(tile("a", "x", { average: null, vote_count: 0 }), true).sub).toBe("ancora nessun voto");
    expect(tileScore(tile("a", "x", { average: null, vote_count: null }), false)).toEqual({
      score: "?",
      sub: "vota per vedere",
    });
    expect(tileStatus(tile("a", "x", { status: "style_rejected" }))).toBe("FUORI STILE");
    expect(tileStatus(tile("a", "x"))).toBeNull();
  });
});

describe("Portfolio", () => {
  test("intestazione, stili, capsule e griglia con la copertina", async () => {
    serve(user());
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    expect(await screen.findByLabelText(/^Fit 1, copertina, Galà, Capodanno/)).toBeOnTheScreen();
    expect(screen.getByLabelText("voto medio: 88")).toBeOnTheScreen();
    expect(screen.getByLabelText("voti ricevuti: 5,1k")).toBeOnTheScreen();
    expect(screen.getByText("PRIVATO")).toBeOnTheScreen();
    expect(screen.getByText("Trento, presto Monaco.")).toBeOnTheScreen();
    expect(screen.getByRole("tab", { name: "Serate, 1 fit" })).toBeOnTheScreen();
    expect(screen.getByLabelText(/^Fit 2, Galà, Teatro/)).toBeOnTheScreen();
    expect(get).toHaveBeenCalledWith("/v1/users/fra.fit/posts?limit=60", expect.objectContaining({ token: "tok" }));
  });

  test("aprire un fit", async () => {
    serve(user());
    const u = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    await u.press(await screen.findByLabelText(/^Fit 2,/));
    expect(router.push).toHaveBeenCalledWith({ pathname: "/post/[id]", params: { id: "p2" } });
  });

  test("riordino con le frecce: subito a schermo, poi salvato", async () => {
    serve(user());
    let resolve: () => void = () => undefined;
    request.mockReturnValue(new Promise<void>((r) => (resolve = r)));
    const u = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    await u.press(await screen.findByRole("button", { name: "Modifica ordine" }));
    expect(screen.getByText(/Il primo è la copertina/)).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Sposta prima: fit 1" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Sposta dopo: fit 3" })).toBeDisabled();

    await u.press(screen.getByRole("button", { name: "Sposta prima: fit 2" }));
    expect(request).toHaveBeenCalledWith("PUT", "/v1/me/portfolio/order", {
      token: "tok",
      body: { post_id: "p2", after_id: null },
    });
    // Prima ancora della risposta: Teatro è primo ed è la copertina.
    expect(screen.getByLabelText(/^Fit 1, copertina, Galà, Teatro/)).toBeOnTheScreen();
    expect(screen.getByLabelText(/^Fit 2, Galà, Capodanno/)).toBeOnTheScreen();

    await u.press(screen.getByRole("button", { name: "Sposta dopo: fit 2" }));
    expect(request).toHaveBeenLastCalledWith("PUT", "/v1/me/portfolio/order", {
      token: "tok",
      body: { post_id: "p1", after_id: "p3" },
    });
    expect(screen.getByLabelText(/^Fit 3, Galà, Capodanno/)).toBeOnTheScreen();
    await act(async () => resolve());
    await u.press(screen.getByRole("button", { name: "Fatto" }));
    expect(screen.queryByRole("button", { name: /Sposta prima/ })).toBeNull();
  });

  test("riordino rifiutato: si torna com'era con il messaggio", async () => {
    serve(user());
    request.mockRejectedValue(new TypeError("Network request failed"));
    const u = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    await u.press(await screen.findByRole("button", { name: "Modifica ordine" }));
    await u.press(screen.getByRole("button", { name: "Sposta prima: fit 3" }));
    expect(await screen.findByText("L'ordine non è stato salvato. Controlla la connessione e riprova.")).toBeOnTheScreen();
    expect(screen.getByLabelText(/^Fit 3, Galà, Ufficio/)).toBeOnTheScreen();
  });

  test("scheda di una capsula: griglia filtrata, niente riordino", async () => {
    serve(user(), (path) => (path.includes("capsule=c1") ? page([TILES[1]!], { cover_id: "p1" }) : page(TILES)));
    const u = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    await u.press(await screen.findByRole("tab", { name: "Serate, 1 fit" }));
    expect(get).toHaveBeenCalledWith("/v1/users/fra.fit/posts?limit=60&capsule=c1", expect.anything());
    expect(await screen.findByLabelText(/^Fit 1, Galà, Teatro/)).toBeOnTheScreen(); // nessuna "copertina" qui
    expect(screen.getByRole("tab", { name: "Serate, 1 fit" })).toBeSelected();
    await u.press(screen.getByRole("button", { name: "Modifica ordine" }));
    // Il riordino riporta a "Tutti".
    expect(screen.getByRole("tab", { name: /^Tutti/ })).toBeSelected();
    expect(screen.getAllByRole("button", { name: /Sposta prima/ })).toHaveLength(3);
  });

  test("portfolio vuoto: invito a pubblicare", async () => {
    serve(user({ stats: { posts: 0, average: null, votes: 0 }, capsules: [] }), page([]));
    const u = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    await u.press(await screen.findByRole("button", { name: "Pubblica un fit" }));
    expect(router.push).toHaveBeenCalledWith("/new-post");
    expect(screen.getByLabelText("voto medio: non disponibile")).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Modifica ordine" })).toBeDisabled();
  });

  test("account privato di un altro: niente griglia", async () => {
    serve(user({ nickname: "altro", is_self: false, can_view_posts: false, styles: [], capsules: [] }));
    await render(<PortfolioScreen nickname="altro" />, { wrapper: Providers });
    expect(await screen.findByText("Account privato")).toBeOnTheScreen();
    expect(screen.queryByRole("button", { name: "Modifica ordine" })).toBeNull();
    expect(get.mock.calls.map((c) => c[0])).toEqual(["/v1/users/altro"]);
  });

  test("profilo che non esiste", async () => {
    serve(new ApiError(404, "user.not_found", "Profilo non trovato"));
    await render(<PortfolioScreen nickname="altro" />, { wrapper: Providers });
    expect(await screen.findByText("Profilo non disponibile")).toBeOnTheScreen();
  });

  test("capsule: crea, nome già usato", async () => {
    serve(user());
    request
      .mockResolvedValueOnce({ id: "c3", name: "Estate", post_count: 0 })
      .mockRejectedValueOnce(new ApiError(409, "capsule.name_taken", "Esiste"));
    const u = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    await u.press(await screen.findByRole("button", { name: "Capsule" }));
    expect(await screen.findByRole("button", { name: "Rinomina Ufficio" })).toBeOnTheScreen();
    const field = screen.getByLabelText(/Nuova capsula · 2 di 12/i);

    await u.type(field, "Estate");
    await u.press(screen.getByRole("button", { name: "Aggiungi" }));
    expect(request).toHaveBeenCalledWith("POST", "/v1/me/capsules", { token: "tok", body: { name: "Estate" } });
    await u.type(screen.getByLabelText(/Nuova capsula/i), "serate");
    await u.press(screen.getByRole("button", { name: "Aggiungi" }));
    expect(await screen.findByText("Hai già una capsula con questo nome.")).toBeOnTheScreen();
  });

  test("capsule: elimina con conferma", async () => {
    serve(user());
    request.mockResolvedValue(undefined);
    const u = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    await u.press(await screen.findByRole("button", { name: "Capsule" }));
    await u.press(await screen.findByRole("button", { name: "Elimina Serate" }));
    expect(screen.getByText(/I fit restano nel portfolio/)).toBeOnTheScreen();
    await u.press(screen.getByRole("button", { name: "Elimina" }));
    expect(request).toHaveBeenCalledWith("DELETE", "/v1/me/capsules/c1", { token: "tok" });
  });
});

describe("Dettaglio del proprio fit", () => {
  const own: Post = {
    id: "p2",
    status: "active",
    style: { slug: "gala", name: "Galà", tone: "#3A1418" },
    author: { nickname: "fra.fit", account_type: "private" },
    is_own: true,
    caption: "Teatro",
    media: [],
    items: [],
    published_at: "2026-10-05T09:00:00Z",
    created_at: "2026-10-05T09:00:00Z",
    restyle_available: true,
    capsule_id: "c1",
    vote: { mine: null, my_style_confirm: null, average: 91, vote_count: 1120, style_match: null, ask_style_confirm: false },
  };

  function servePost(post: Post | Error) {
    get.mockImplementation((path: string) => {
      if (path === "/v1/posts/p2") return post instanceof Error ? Promise.reject(post) : Promise.resolve(post);
      if (path === "/v1/me/capsules") return Promise.resolve(CAPSULES);
      if (path.startsWith("/v1/users/fra.fit/posts")) return Promise.resolve(page(TILES));
      return Promise.reject(new Error(`percorso inatteso ${path}`));
    });
  }

  test("capsula: cambia", async () => {
    servePost(own);
    request.mockResolvedValue({ ...own, capsule_id: "c2" });
    const u = userEvent.setup();
    await render(<PostScreen />, { wrapper: Providers });
    await u.press(await screen.findByRole("button", { name: "Capsula: Serate" }));
    await u.press(await screen.findByRole("radio", { name: "Ufficio" }));
    expect(request).toHaveBeenCalledWith("PATCH", "/v1/posts/p2", { token: "tok", body: { capsule_id: "c2" } });
    expect(await screen.findByText("Fit aggiunto alla capsula.")).toBeOnTheScreen();
    expect(await screen.findByRole("button", { name: "Capsula: Ufficio" })).toBeOnTheScreen();
  });

  test("metti in copertina", async () => {
    servePost(own);
    request.mockResolvedValue(undefined);
    const u = userEvent.setup();
    await render(<PostScreen />, { wrapper: Providers });
    await u.press(await screen.findByRole("button", { name: "Metti in copertina" }));
    expect(request).toHaveBeenCalledWith("PUT", "/v1/me/portfolio/order", {
      token: "tok",
      body: { post_id: "p2", after_id: null },
    });
    expect(await screen.findByText("Ora è la copertina del tuo portfolio.")).toBeOnTheScreen();
  });

  test("copertina già: pulsante spento", async () => {
    servePost({ ...own, id: "p2" });
    get.mockImplementation((path: string) => {
      if (path === "/v1/posts/p2") return Promise.resolve(own);
      if (path === "/v1/me/capsules") return Promise.resolve(CAPSULES);
      return Promise.resolve(page([TILES[1]!, TILES[0]!]));
    });
    await render(<PostScreen />, { wrapper: Providers });
    expect(await screen.findByRole("button", { name: "È la copertina del portfolio" })).toBeDisabled();
  });

  test("elimina con conferma e torna indietro", async () => {
    servePost(own);
    request.mockResolvedValue(undefined);
    const u = userEvent.setup();
    await render(<PostScreen />, { wrapper: Providers });
    await u.press(await screen.findByRole("button", { name: "Elimina fit" }));
    expect(screen.getByText(/Non si può annullare/)).toBeOnTheScreen();
    await u.press(screen.getByRole("button", { name: "Elimina" }));
    expect(request).toHaveBeenCalledWith("DELETE", "/v1/posts/p2", { token: "tok" });
    expect(router.back).toHaveBeenCalled();
  });

  test("fit non più disponibile", async () => {
    servePost(new ApiError(404, "post.not_found", "Non trovato"));
    await render(<PostScreen />, { wrapper: Providers });
    expect(await screen.findByText("Fit non disponibile")).toBeOnTheScreen();
  });
});

describe("profilo (seduta 27)", () => {
  test("il proprio: i suoi stili, Modifica profilo, invito alla bio", async () => {
    serve(user({ bio: null }));
    const u = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    expect(await screen.findByLabelText("I tuoi stili: Galà")).toBeOnTheScreen();
    await u.press(screen.getByRole("link", { name: "+ Aggiungi una bio" }));
    expect(router.push).toHaveBeenLastCalledWith("/edit-profile");
    await u.press(screen.getByRole("button", { name: "Modifica profilo" }));
    await u.press(screen.getByRole("button", { name: "Modifica la foto profilo" }));
    expect(router.push).toHaveBeenCalledTimes(3);
  });

  test("quello di un altro: niente stili né modifica, la foto profilo se c'è", async () => {
    serve(
      user({
        nickname: "altro",
        is_self: false,
        styles: [],
        avatar: { blurhash: "LEHV6nWB2yk8pyo0adR*.7kCMdnj", urls: { variants: { "320": "https://cdn/a-320.webp" }, expires_at: "2026-10-10T20:00:00Z" } },
      }),
    );
    await render(<PortfolioScreen nickname="altro" />, { wrapper: Providers });
    expect(await screen.findByText("@altro")).toBeOnTheScreen();
    expect(screen.queryByLabelText(/^I tuoi stili/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Modifica profilo" })).toBeNull();
    // La foto è decorativa (nascosta ai lettori di schermo): il nome è già nel profilo.
    expect(screen.getByTestId("avatar-photo", { includeHiddenElements: true })).toBeTruthy();
  });
});

describe("portfolio da designer (seduta 28)", () => {
  test("capsule più grandi quanti più fit contengono", () => {
    expect([0, 1, 2, 4, 5, 9, 10, 40].map(capsuleWidth)).toEqual([92, 92, 116, 116, 144, 144, 176, 176]);
    expect(CAPSULE_SIZES.map((s) => s.width)).toEqual([...CAPSULE_SIZES.map((s) => s.width)].sort((a, b) => a - b));
    expect(shelfHeight([])).toBe(115);
    expect(shelfHeight([{ post_count: 1 }, { post_count: 12 }])).toBe(220);
  });

  test("la copertina apre il portfolio a tutta larghezza; nelle capsule la griglia è uniforme", async () => {
    serve(user({ capsules: [{ id: "c1", name: "Serate", post_count: 6, cover: null }] }), (path) =>
      path.includes("capsule=c1") ? page([tile("p2", "Teatro")]) : page(TILES),
    );
    const u = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    const cover = await screen.findByLabelText(/^Fit 1, copertina, Galà, Capodanno/);
    const second = screen.getByLabelText(/^Fit 2, Galà, Teatro/);
    // Finestra di prova larga 750: contenuto al massimo 560, meno 2 x 16 di margine = 528 per la
    // copertina; gli altri in due colonne da 260.
    const widthOf = (el: typeof cover) => {
      let node: typeof cover | null = el;
      while (node && !(node.props.style && [node.props.style].flat().some((st: { width?: number }) => st?.width))) node = node.parent;
      return [node!.props.style].flat().find((st: { width?: number }) => st?.width)!.width as number;
    };
    expect(widthOf(cover)).toBe(528);
    expect(widthOf(second)).toBe(260);
    expect(screen.getByText("PORTFOLIO · 3 FIT")).toBeOnTheScreen();

    const shelfTab = screen.getByRole("tab", { name: "Serate, 6 fit" });
    expect(shelfTab).toHaveStyle({ width: 144 });
    await u.press(shelfTab);
    expect(await screen.findByText("SERATE · 6 FIT")).toBeOnTheScreen();
    expect(widthOf(await screen.findByLabelText(/^Fit 1, Galà, Teatro/))).toBe(260);
  });
});
