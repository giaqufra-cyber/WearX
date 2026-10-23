import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PortfolioTile, Post } from "@wearx/api-types";
import { render, screen, userEvent, waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import ArchiveScreen from "@/app/archive";
import PostScreen from "@/app/post/[id]";
import SavedScreen from "@/app/saved";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), navigate: jest.fn(), canGoBack: () => true },
  useLocalSearchParams: jest.fn(() => ({ id: "p1" })),
}));
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({ session: { access_token: "tok", user: { id: "u1" } }, profile: { nickname: "fra.fit" } }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;

const post = (extra: Partial<Post> = {}): Post => ({
  id: "p1",
  status: "active",
  saved: false,
  style: { slug: "gala", name: "Galà", tone: "#3A1418" },
  author: { nickname: "negozio", account_type: "business" },
  is_own: false,
  caption: "Teatro",
  media: [],
  items: [],
  published_at: "2026-10-05T09:00:00Z",
  created_at: "2026-10-05T09:00:00Z",
  vote: { mine: null, my_style_confirm: null, average: null, vote_count: null, style_match: null, ask_style_confirm: false },
  ...extra,
});

const tile = (id: string, extra: Partial<PortfolioTile> = {}): PortfolioTile => ({
  id,
  status: "active",
  style: { slug: "gala", name: "Galà", tone: "#3A1418" },
  caption: null,
  capsule_id: null,
  media_count: 1,
  photo: null,
  mine: null,
  average: null,
  vote_count: null,
  own: false,
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

function serve(current: Post) {
  get.mockImplementation((path: string) => {
    if (path === "/v1/posts/p1") return Promise.resolve(current);
    if (path === "/v1/me/capsules") return Promise.resolve([]);
    if (path.startsWith("/v1/users/fra.fit/posts")) return Promise.resolve({ items: [], next_cursor: null, cover_id: null });
    return Promise.reject(new Error(`percorso inatteso ${path}`));
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });
});
afterEach(() => client.clear());

test("salva un fit altrui: il segnalibro si riempie subito", async () => {
  serve(post());
  request.mockResolvedValue({ saved: true });
  const u = userEvent.setup();
  await render(<PostScreen />, { wrapper: Providers });
  await u.press(await screen.findByRole("button", { name: "Salva il fit" }));
  expect(request).toHaveBeenCalledWith("PUT", "/v1/posts/p1/save", { token: "tok" });
  expect(await screen.findByRole("button", { name: "Togli dai salvati" })).toBeOnTheScreen();
  expect(await screen.findByText("Salvato. Lo ritrovi nel tuo profilo, in Salvati.")).toBeOnTheScreen();

  request.mockResolvedValue(undefined);
  await u.press(screen.getByRole("button", { name: "Togli dai salvati" }));
  expect(request).toHaveBeenLastCalledWith("DELETE", "/v1/posts/p1/save", { token: "tok" });
  expect(await screen.findByRole("button", { name: "Salva il fit" })).toBeOnTheScreen();
});

test("salvataggio non riuscito: torna com'era", async () => {
  serve(post());
  request.mockRejectedValue(new ApiError(404, "post.not_found", "Post non trovato"));
  const u = userEvent.setup();
  await render(<PostScreen />, { wrapper: Providers });
  await u.press(await screen.findByRole("button", { name: "Salva il fit" }));
  expect(await screen.findByText("Questo fit non è più disponibile.")).toBeOnTheScreen();
  expect(screen.getByRole("button", { name: "Salva il fit" })).toBeOnTheScreen();
});

test("proprio fit: niente segnalibro; archivia e rimetti", async () => {
  const own = post({ is_own: true, author: { nickname: "fra.fit", account_type: "private" }, archived: false, save_count: 3 });
  serve(own);
  request.mockResolvedValue({ ...own, archived: true });
  const u = userEvent.setup();
  await render(<PostScreen />, { wrapper: Providers });
  expect(await screen.findByText("Salvato da 3 persone")).toBeOnTheScreen();
  expect(screen.queryByRole("button", { name: "Salva il fit" })).toBeNull();

  await u.press(screen.getByRole("button", { name: "Archivia" }));
  expect(request).toHaveBeenCalledWith("POST", "/v1/posts/p1/archive", { token: "tok" });
  expect(await screen.findByText("Archiviato")).toBeOnTheScreen();
  expect(screen.getByText("Fit archiviato. Lo ritrovi in Account → Archivio.")).toBeOnTheScreen();
  // In archivio non si mette in copertina.
  expect(screen.queryByRole("button", { name: "Metti in copertina" })).toBeNull();

  request.mockResolvedValue({ ...own, archived: false });
  await u.press(screen.getByRole("button", { name: "Rimetti nel profilo" }));
  expect(request).toHaveBeenLastCalledWith("DELETE", "/v1/posts/p1/archive", { token: "tok" });
  await waitFor(() => expect(screen.queryByText("Archiviato")).toBeNull());
  expect(screen.getByRole("button", { name: "Metti in copertina" })).toBeOnTheScreen();
});

test("Salvati: griglia con l'autore, e si apre il fit", async () => {
  get.mockResolvedValue({
    items: [tile("a", { author: { nickname: "negozio", account_type: "business" } }), tile("b")],
    next_cursor: null,
  });
  const u = userEvent.setup();
  await render(<SavedScreen />, { wrapper: Providers });
  expect(get).toHaveBeenCalledWith("/v1/me/saved", expect.objectContaining({ token: "tok" }));
  expect(await screen.findByText("@negozio")).toBeOnTheScreen();
  await u.press(screen.getByRole("button", { name: "Fit, @negozio, Galà" }));
  expect(router.push).toHaveBeenCalledWith({ pathname: "/post/[id]", params: { id: "a" } });
});

test("Salvati e Archivio vuoti", async () => {
  get.mockResolvedValue({ items: [], next_cursor: null });
  const first = await render(<SavedScreen />, { wrapper: Providers });
  expect(await screen.findByText("Ancora nessun fit salvato")).toBeOnTheScreen();
  first.unmount();
  await render(<ArchiveScreen />, { wrapper: Providers });
  expect(await screen.findByText("L'archivio è vuoto")).toBeOnTheScreen();
  expect(get).toHaveBeenCalledWith("/v1/me/archive", expect.objectContaining({ token: "tok" }));
});
