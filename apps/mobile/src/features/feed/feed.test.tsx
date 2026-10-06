import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { FeedPage, Post, VoteSummary } from "@wearx/api-types";
import { act, fireEvent, render, screen, userEvent } from "@testing-library/react-native";
import * as WebBrowser from "expo-web-browser";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import FeedScreen from "@/app/(tabs)/index";
import { useFeed } from "@/features/feed/api";
import { bestVariant, initials, matchLabel, totalPrice, votesLabel } from "@/features/feed/format";
import { clampScore, scoreAt, scoreForKey } from "@/features/feed/VoteSlider";
import { photoLabel } from "@/features/feed/Carousel";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), navigate: jest.fn(), canGoBack: () => true },
}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn(() => Promise.resolve({ type: "opened" })) }));
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({ session: { access_token: "tok", user: { id: "u1" } } }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;

const vote = (extra: Partial<VoteSummary> = {}): VoteSummary => ({
  mine: null,
  my_style_confirm: null,
  average: null,
  vote_count: null,
  style_match: null,
  ask_style_confirm: false,
  ...extra,
});

const media = (position: number) => ({
  position,
  width: 1080,
  height: 1350,
  blurhash: "LEHV6nWB2yk8pyo0adR*.7kCMdnj",
  urls: { variants: { "320": `https://cdn/${position}/320.webp`, "1080": `https://cdn/${position}/1080.webp` }, expires_at: "2026-10-05T12:00:00Z" },
});

const post = (id: string, extra: Partial<Post> = {}): Post => ({
  id,
  status: "active",
  style: { slug: "gala", name: "Galà", tone: "#3A1418" },
  author: { nickname: "giulia.rossi", account_type: "private" },
  is_own: false,
  caption: "Prima del gala",
  media: [media(0), media(1)],
  items: [
    {
      position: 0,
      brand: "Armani",
      name: "Smoking in lana",
      price_cents: 189_000,
      currency: "EUR",
      link: {
        id: "l1",
        domain: "armani.com",
        status: "safe",
        url: "https://www.armani.com/smoking",
        go_url: "http://localhost:8000/r/firmato",
        verified: false,
      },
      media_position: 0,
      pin_x: 0.5,
      pin_y: 0.3,
    },
    {
      position: 1,
      brand: "Church's",
      name: "Derby lucide",
      price_cents: 59_000,
      currency: "EUR",
      link: null,
      media_position: 1,
      pin_x: 0.4,
      pin_y: 0.9,
    },
  ],
  published_at: "2026-10-05T09:00:00Z",
  created_at: "2026-10-05T09:00:00Z",
  vote: vote(),
  ...extra,
});

const page = (items: Post[], extra: Partial<FeedPage> = {}): FeedPage => ({ items, next_cursor: null, ...extra });

const MY_STYLES = {
  items: [{ slug: "gala", name: "Galà", tagline: "", tone: "#3A1418", min_age_band: "16_17", seasonal: false, active_until: null, member_count: 3, joined: true }],
  total: 1,
};

/** apiGet finto per percorso: stili miei + le pagine di feed date in ordine. */
function serve(...pages: (FeedPage | Error)[]) {
  get.mockImplementation((path: string) => {
    if (path.startsWith("/v1/me/styles")) return Promise.resolve(MY_STYLES);
    if (path.startsWith("/v1/feed")) {
      const next = pages.length > 1 ? pages.shift()! : pages[0]!;
      return next instanceof Error ? Promise.reject(next) : Promise.resolve(next);
    }
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

describe("testi e calcoli", () => {
  test("iniziali, match, totale, voti", () => {
    expect(initials("giulia.rossi")).toBe("GR");
    expect(initials("marco_atelier")).toBe("MA");
    expect(initials("studio")).toBe("ST");
    expect(initials(undefined)).toBe("");
    expect(matchLabel(0.966)).toBe("97% match");
    expect(matchLabel(null)).toBeNull();
    expect(votesLabel(1)).toBe("1 voto");
    expect(votesLabel(12_345)).toBe("12.345 voti");
    const items = post("p").items;
    expect(totalPrice(items)).toBe("2.480 €");
    expect(totalPrice(items.map((i) => ({ ...i, price_cents: null })))).toBeNull();
    // Le valute diverse dall'euro non si sommano.
    expect(totalPrice([{ ...items[0]!, currency: "USD" }])).toBeNull();
  });

  test("variante: la più piccola che basta, altrimenti la più grande", () => {
    const v = { "1080": "L", "320": "S", "640": "M" };
    expect(bestVariant(v, 300)).toBe("S");
    expect(bestVariant(v, 321)).toBe("M");
    expect(bestVariant(v, 3000)).toBe("L");
    expect(bestVariant({}, 300)).toBeUndefined();
  });

  test("slider: posizione -> voto sempre tra 1 e 100", () => {
    expect(scoreAt(0, 300)).toBe(1);
    expect(scoreAt(300, 300)).toBe(100);
    expect(scoreAt(150, 300)).toBe(51);
    expect(scoreAt(-40, 300)).toBe(1);
    expect(scoreAt(900, 300)).toBe(100);
    expect(scoreAt(10, 0)).toBe(1);
    expect(clampScore(0)).toBe(1);
    expect(clampScore(100.4)).toBe(100);
  });

  test("slider da tastiera (web): frecce, pagina su/giù, inizio e fine", () => {
    expect(scoreForKey("ArrowRight", 70)).toBe(71);
    expect(scoreForKey("ArrowDown", 70)).toBe(69);
    expect(scoreForKey("PageUp", 95)).toBe(100);
    expect(scoreForKey("PageDown", 5)).toBe(1);
    expect(scoreForKey("Home", 70)).toBe(1);
    expect(scoreForKey("End", 70)).toBe(100);
    expect(scoreForKey("a", 70)).toBeNull();
  });
});

describe("Feed", () => {
  test("card con autore, stile, match, capi, totale e link al negozio", async () => {
    serve(page([post("p1", { vote: vote({ style_match: 0.97 }) })]));
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });

    expect(await screen.findByLabelText("@giulia.rossi, Galà")).toBeOnTheScreen();
    expect(screen.getByText("97% match")).toBeOnTheScreen();
    expect(screen.getByText("TOTALE 2.480 €")).toBeOnTheScreen();
    expect(screen.getByText("Smoking in lana")).toBeOnTheScreen();
    expect(screen.getByText("1/2")).toBeOnTheScreen();
    expect(get).toHaveBeenCalledWith("/v1/feed", expect.objectContaining({ token: "tok" }));

    await user.press(screen.getByRole("link", { name: "Apri armani.com" }));
    expect(WebBrowser.openBrowserAsync).toHaveBeenCalledWith("http://localhost:8000/r/firmato");
    // Il capo senza link non ha il pulsante.
    expect(screen.queryAllByRole("link", { name: /^Apri [a-z0-9.-]+\.[a-z]+$/ })).toHaveLength(1);
    // Il nome dell'autore apre il suo profilo.
    await user.press(screen.getByRole("link", { name: "Apri il profilo di @giulia.rossi" }));
    expect(router.push).toHaveBeenCalledWith({ pathname: "/user/[nickname]", params: { nickname: "giulia.rossi" } });
  });

  test("anonimo e post proprio", async () => {
    serve(
      page([
        post("p1", { author: null }),
        post("p2", { is_own: true, author: { nickname: "fra", account_type: "private" }, vote: vote({ average: 81.4, vote_count: 12 }) }),
      ]),
    );
    await render(<FeedScreen />, { wrapper: Providers });
    expect(await screen.findByText("Fit anonimo")).toBeOnTheScreen();
    expect(screen.getByText("IL TUO FIT · MEDIA")).toBeOnTheScreen();
    expect(screen.getByLabelText("Media 81.4")).toHaveTextContent("81");
    expect(screen.getByText(/12 voti/)).toBeOnTheScreen();
  });

  test("i capi sulla foto si mostrano e nascondono", async () => {
    serve(page([post("p1")]));
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Mostra i capi sulla foto" }));
    // Il marchio compare anche sulla foto (oltre che nella lista dei capi).
    expect(screen.getAllByText("Armani")).toHaveLength(2);
    expect(screen.getAllByText("Church's")).toHaveLength(1); // è sulla seconda foto
    await user.press(screen.getByRole("button", { name: "Nascondi i capi sulla foto" }));
    expect(screen.getAllByText("Armani")).toHaveLength(1);
  });

  test("voto: si vede subito, poi arriva la media; conferma dello stile inviata", async () => {
    serve(page([post("p1", { vote: vote({ ask_style_confirm: true }) })]));
    let resolve: (value: VoteSummary) => void = () => undefined;
    request.mockReturnValue(new Promise<VoteSummary>((r) => (resolve = r)));
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });

    const slider = await screen.findByRole("slider", { name: "Il tuo voto da 1 a 100" });
    await fireEvent(slider, "accessibilityAction", { nativeEvent: { actionName: "increment" } });
    await user.press(screen.getByRole("button", { name: "Un punto in più" }));
    expect(screen.getByText("72")).toBeOnTheScreen();
    await user.press(screen.getByRole("radio", { name: "Sì" }));
    await user.press(screen.getByRole("button", { name: "Vota" }));

    expect(request).toHaveBeenCalledWith("PUT", "/v1/posts/p1/vote", { token: "tok", body: { score: 72, style_confirm: true } });
    // Prima della risposta: il voto è già registrato, la media è in arrivo.
    expect(screen.getByText("MEDIA COMMUNITY")).toBeOnTheScreen();
    expect(screen.getByLabelText("Media non ancora disponibile")).toHaveTextContent("…");

    await act(async () =>
      resolve(
        vote({
          mine: 72,
          my_style_confirm: true,
          average: 88.2,
          vote_count: 41,
          stats_updated_at: "2026-10-05T19:05:00Z",
        }),
      ),
    );
    expect(await screen.findByLabelText("Media 88.2")).toHaveTextContent("88");
    expect(screen.getByText(/41 voti/)).toBeOnTheScreen();
    // Media e numero sono quelli pubblicati ogni ora (l'orario dipende dal fuso del telefono).
    expect(screen.getByText(/^Voti aggiornati ogni ora · ultimo alle \d\d:05$/)).toBeOnTheScreen();
  });

  test("senza domanda sullo stile non si manda la conferma", async () => {
    serve(page([post("p1")]));
    request.mockResolvedValue(vote({ mine: 70, average: null, vote_count: 1, average_note: "few_votes" }));
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });
    expect(screen.queryByRole("radio", { name: "Sì" })).toBeNull();
    await user.press(await screen.findByRole("button", { name: "Vota" }));
    expect(request).toHaveBeenCalledWith("PUT", "/v1/posts/p1/vote", { token: "tok", body: { score: 70 } });
    expect(await screen.findByText(/1 voto/)).toBeOnTheScreen();
    expect(screen.getByText("La media compare da 5 voti · si aggiornano ogni ora")).toBeOnTheScreen();
    expect(screen.getByLabelText("Media non ancora disponibile")).toHaveTextContent("–");
  });

  test("voto rifiutato: si torna com'era, con il messaggio", async () => {
    serve(page([post("p1")]));
    request.mockRejectedValue(new ApiError(404, "post.not_found", "Non trovato"));
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Vota" }));
    expect(await screen.findByText("Questo fit non è più disponibile.")).toBeOnTheScreen();
    expect(screen.getByText("VOTA IL FIT · 1–100")).toBeOnTheScreen();
    expect(screen.queryByText("MEDIA COMMUNITY")).toBeNull();
  });

  test("pagine successive, senza doppioni", async () => {
    serve(page([post("p1")], { next_cursor: "c1" }), page([post("p1"), post("p2", { caption: "Secondo fit" })]));
    // Arrivati in fondo la lista chiama fetchNextPage: qui lo si chiama dallo stesso hook (stessa cache).
    let feed: ReturnType<typeof useFeed> | undefined;
    function Harness() {
      feed = useFeed(null);
      return <FeedScreen />;
    }
    await render(<Harness />, { wrapper: Providers });
    await screen.findByLabelText("@giulia.rossi, Galà");
    await act(async () => {
      await feed!.fetchNextPage();
    });
    expect(get).toHaveBeenCalledWith("/v1/feed?cursor=c1", expect.anything());
    expect(await screen.findByText(/Secondo fit/)).toBeOnTheScreen();
    expect(screen.getAllByLabelText(/, Galà$/)).toHaveLength(2);
  });

  test("filtro per stile: chiede il feed di quello stile", async () => {
    serve(page([post("p1")]));
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });
    await user.press(await screen.findByRole("tab", { name: "Galà" }));
    expect(get).toHaveBeenCalledWith("/v1/feed?style=gala", expect.anything());
  });

  test("nessuno stile: invito a sceglierli", async () => {
    serve(page([], { empty_reason: "no_styles" }));
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });
    expect(await screen.findByText("Scegli i tuoi stili")).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Esplora gli stili" }));
    expect(router.navigate).toHaveBeenCalledWith("/explore");
  });

  test("visto tutto: invito a pubblicare", async () => {
    serve(page([], { empty_reason: "no_posts" }));
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Pubblica un fit" }));
    expect(router.push).toHaveBeenCalledWith("/new-post");
  });

  test("errore di rete con Riprova", async () => {
    serve(new TypeError("Network request failed"), page([post("p1")]));
    const user = userEvent.setup();
    await render(<FeedScreen />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Riprova" }));
    expect(await screen.findByLabelText("@giulia.rossi, Galà")).toBeOnTheScreen();
  });
});

describe("descrizione delle foto per i lettori di schermo", () => {
  test("dice di chi è il fit e quale foto è, senza ripetere la didascalia", () => {
    expect(photoLabel(0, 1, "@giulia")).toBe("Foto del fit di @giulia");
    expect(photoLabel(1, 3, "@giulia")).toBe("Foto 2 di 3, fit di @giulia");
    expect(photoLabel(0, 1, "Fit anonimo")).toBe("Foto del fit anonimo");
  });
});
