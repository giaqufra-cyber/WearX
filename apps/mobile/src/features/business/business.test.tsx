import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Post, ShopDomain } from "@wearx/api-types";
import { fireEvent, render, screen, userEvent } from "@testing-library/react-native";
import * as WebBrowser from "expo-web-browser";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import AccountTypeScreen from "@/app/account-type";
import ShopDomainsScreen from "@/app/shop-domains";
import { PostCard } from "@/features/feed/PostCard";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: () => true },
}));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
const mockProfile: { account_type: "private" | "business"; age_band: "16_17" | "18_plus"; nickname: string } = {
  account_type: "private",
  age_band: "18_plus",
  nickname: "studio.nove",
};
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({ session: { access_token: "tok", user: { id: "u1" } }, profile: mockProfile }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;

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
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  mockProfile.account_type = "private";
  mockProfile.age_band = "18_plus";
});
afterEach(() => client.clear());

const post = (): Post => ({
  id: "p1",
  status: "active",
  style: { slug: "gala", name: "Galà", tone: "#3A1418" },
  author: { nickname: "studio.nove", account_type: "business" },
  is_own: false,
  caption: null,
  media: [],
  items: [
    {
      position: 0,
      brand: "Studio Nove",
      name: "Blazer",
      price_cents: 32_000,
      currency: "EUR",
      link: {
        id: "l1",
        domain: "studionove.it",
        status: "safe",
        url: "https://studionove.it/blazer",
        go_url: "http://localhost:8000/r/aaa",
        verified: true,
      },
      media_position: null,
      pin_x: null,
      pin_y: null,
    },
    {
      position: 1,
      brand: "Vintage",
      name: "Borsa",
      price_cents: null,
      currency: "EUR",
      link: { id: "l2", domain: "vecchio.it", status: "broken", url: "https://vecchio.it/x", go_url: "http://x/r/b", verified: false },
      media_position: null,
      pin_x: null,
      pin_y: null,
    },
    {
      position: 2,
      brand: "Outlet",
      name: "Mocassini",
      price_cents: 3900,
      currency: "EUR",
      link: { id: "l3", domain: "falso.com", status: "blocked", url: null, go_url: null, verified: false },
      media_position: null,
      pin_x: null,
      pin_y: null,
    },
  ],
  published_at: null,
  created_at: "2026-10-05T08:00:00Z",
  vote: { mine: null, my_style_confirm: null, average: null, vote_count: null, style_match: null, ask_style_confirm: false },
});

test("capi: negozio verificato, link via redirect, link non più disponibile", async () => {
  const user = userEvent.setup();
  await render(<PostCard post={post()} width={390} onVote={jest.fn()} voting={false} />, { wrapper: Providers });
  expect(screen.getByLabelText("Negozio verificato")).toBeOnTheScreen();
  await user.press(screen.getByRole("link", { name: "Apri studionove.it" }));
  expect(WebBrowser.openBrowserAsync).toHaveBeenCalledWith("http://localhost:8000/r/aaa");
  expect(screen.getByText("Link non più disponibile")).toBeOnTheScreen();
  expect(screen.queryByRole("link", { name: "Apri vecchio.it" })).toBeNull();
  expect(screen.getByText("Link rimosso per sicurezza")).toBeOnTheScreen();
  expect(screen.queryByRole("link", { name: "Apri falso.com" })).toBeNull();
});

test("tipo di account: Business con conferma", async () => {
  request.mockResolvedValue({ ...mockProfile, account_type: "business" });
  const user = userEvent.setup();
  await render(<AccountTypeScreen />, { wrapper: Providers });
  await user.press(screen.getByRole("radio", { name: "Business" }));
  expect(screen.getByText(/Profilo pubblico/)).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Passa a Business" }));
  expect(request).not.toHaveBeenCalled();
  await user.press(screen.getByRole("button", { name: "Conferma" }));
  expect(request).toHaveBeenCalledWith("PATCH", "/v1/me", { token: "tok", body: { account_type: "business" } });
  expect(router.replace).toHaveBeenCalledWith("/shop-domains");
});

test("tipo di account: i 16-17 restano privati", async () => {
  mockProfile.age_band = "16_17";
  await render(<AccountTypeScreen />, { wrapper: Providers });
  expect(screen.getByText(/sono per maggiorenni/)).toBeOnTheScreen();
  expect(screen.queryByRole("radio", { name: "Business" })).toBeNull();
});

const domain = (extra: Partial<ShopDomain> = {}): ShopDomain => ({
  domain: "studionove.it",
  verified: false,
  verified_at: null,
  file_url: "https://studionove.it/.well-known/wearx-verify.txt",
  file_content: "wearx-verify=abc123",
  ...extra,
});

test("negozi: istruzioni, verifica fallita spiegata, aggiunta", async () => {
  mockProfile.account_type = "business";
  get.mockResolvedValue([domain()]);
  request.mockRejectedValueOnce(
    new ApiError(422, "shop.verify_failed", "no", undefined, { detail: "Il file non c'è o non contiene il codice." }),
  );
  const user = userEvent.setup();
  await render(<ShopDomainsScreen />, { wrapper: Providers });
  expect(await screen.findByText("https://studionove.it/.well-known/wearx-verify.txt")).toBeOnTheScreen();
  expect(screen.getByText("wearx-verify=abc123")).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Verifica" }));
  expect(request).toHaveBeenCalledWith("POST", "/v1/me/shop-domains/studionove.it/verify", { token: "tok" });
  expect(await screen.findByText("Verifica non riuscita. Il file non c'è o non contiene il codice.")).toBeOnTheScreen();

  request.mockResolvedValueOnce(domain({ domain: "nove.shop" }));
  await fireEvent.changeText(screen.getByLabelText("AGGIUNGI UN SITO"), "https://www.nove.shop");
  await user.press(screen.getByRole("button", { name: "Aggiungi" }));
  expect(request).toHaveBeenCalledWith("POST", "/v1/me/shop-domains", { token: "tok", body: { domain: "https://www.nove.shop" } });
});

test("negozi: verificato", async () => {
  mockProfile.account_type = "business";
  get.mockResolvedValue([domain({ verified: true, verified_at: "2026-10-05T10:00:00Z" })]);
  await render(<ShopDomainsScreen />, { wrapper: Providers });
  expect(await screen.findByText("VERIFICATO")).toBeOnTheScreen();
  expect(screen.queryByRole("button", { name: "Verifica" })).toBeNull();
});
