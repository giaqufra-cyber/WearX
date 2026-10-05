import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PeoplePage, UserProfile } from "@wearx/api-types";
import { act, render, screen, userEvent } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import FindScreen from "@/app/find";
import PeopleScreen from "@/app/people";
import { PortfolioScreen } from "@/features/portfolio/PortfolioScreen";
import { followLabel } from "@/features/social/api";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), navigate: jest.fn(), canGoBack: () => true },
  useLocalSearchParams: jest.fn(() => ({})),
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

const { router, useLocalSearchParams } = jest.requireMock("expo-router") as {
  router: Record<string, jest.Mock>;
  useLocalSearchParams: jest.Mock;
};
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;

const person = (extra: Partial<UserProfile> = {}): UserProfile => ({
  verified_domains: [],
  nickname: "giulia.rossi",
  bio: null,
  account_type: "private",
  is_self: false,
  can_view_posts: false,
  styles: [],
  stats: { posts: 4, average: null, votes: null },
  capsules: [],
  followers: 120,
  following: 80,
  relationship: { following: "none", follows_you: false },
  pending_requests: null,
  ...extra,
});

const people = (...nicknames: string[]): PeoplePage => ({
  items: nicknames.map((nickname) => ({ nickname, account_type: "private", since: "2026-10-05T08:00:00Z" })),
  next_cursor: null,
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
  useLocalSearchParams.mockReturnValue({});
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });
});
afterEach(() => client.clear());

test("testo del pulsante Segui", () => {
  expect(followLabel("none", false)).toBe("Segui");
  expect(followLabel("none", true)).toBe("Segui anche tu");
  expect(followLabel("pending", false)).toBe("Richiesta inviata");
  expect(followLabel("accepted", true)).toBe("Segui già");
});

describe("Profilo di un'altra persona", () => {
  test("privato: Segui manda la richiesta, si vede subito; toccare di nuovo la ritira", async () => {
    // Il "server": lo stato del follow cambia con le richieste.
    let following: "none" | "pending" = "none";
    get.mockImplementation(() => Promise.resolve(person({ relationship: { following, follows_you: false } })));
    let resolve: (v: { following: string }) => void = () => undefined;
    request.mockReturnValueOnce(new Promise((r) => (resolve = r))).mockResolvedValueOnce(undefined);
    const user = userEvent.setup();
    await render(<PortfolioScreen nickname="giulia.rossi" />, { wrapper: Providers });

    expect(await screen.findByText("Account privato")).toBeOnTheScreen();
    expect(screen.getByLabelText("120 follower")).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Segui" }));
    expect(request).toHaveBeenCalledWith("POST", "/v1/users/giulia.rossi/follow", { token: "tok" });
    // Prima ancora della risposta del server.
    expect(await screen.findByRole("button", { name: "Richiesta inviata" })).toBeOnTheScreen();
    following = "pending";
    await act(async () => resolve({ following: "pending" }));
    expect(await screen.findByText("Richiesta inviata a @giulia.rossi.")).toBeOnTheScreen();

    following = "none";
    await user.press(await screen.findByRole("button", { name: "Richiesta inviata" }));
    expect(request).toHaveBeenLastCalledWith("DELETE", "/v1/users/giulia.rossi/follow", { token: "tok" });
    expect(await screen.findByRole("button", { name: "Segui" })).toBeOnTheScreen();
  });

  test("errore: il pulsante torna com'era", async () => {
    get.mockResolvedValue(person());
    request.mockRejectedValue(new ApiError(429, "rate.limited", "Troppe"));
    const user = userEvent.setup();
    await render(<PortfolioScreen nickname="giulia.rossi" />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Segui" }));
    expect(await screen.findByText("Troppe azioni in poco tempo: riprova più tardi.")).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Segui" })).toBeOnTheScreen();
  });

  test("business: si segue subito", async () => {
    get.mockImplementation((path: string) =>
      Promise.resolve(
        path.includes("/posts")
          ? { items: [], next_cursor: null, cover_id: null }
          : person({ account_type: "business", can_view_posts: true }),
      ),
    );
    request.mockReturnValue(new Promise(() => undefined));
    const user = userEvent.setup();
    await render(<PortfolioScreen nickname="giulia.rossi" />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Segui" }));
    expect(await screen.findByRole("button", { name: "Segui già" })).toBeOnTheScreen();
  });

  test("smettere di seguire un privato chiede conferma", async () => {
    get.mockImplementation((path: string) =>
      Promise.resolve(
        path.includes("/posts")
          ? { items: [], next_cursor: null, cover_id: null }
          : person({ can_view_posts: true, relationship: { following: "accepted", follows_you: true } }),
      ),
    );
    request.mockResolvedValue(undefined);
    const user = userEvent.setup();
    await render(<PortfolioScreen nickname="giulia.rossi" />, { wrapper: Providers });
    expect(await screen.findByText("TI SEGUE")).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Segui già" }));
    expect(request).not.toHaveBeenCalled();
    expect(screen.getByText(/non vedrai più il suo portfolio/)).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Smetti di seguire" }));
    expect(request).toHaveBeenCalledWith("DELETE", "/v1/users/giulia.rossi/follow", { token: "tok" });
  });

  test("blocca dal menu, con conferma", async () => {
    get.mockResolvedValue(person());
    request.mockResolvedValue(undefined);
    const user = userEvent.setup();
    await render(<PortfolioScreen nickname="giulia.rossi" />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Altre azioni" }));
    await user.press(screen.getByRole("button", { name: "Blocca" }));
    expect(screen.getByText(/Non vi vedrete più/)).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Blocca @giulia.rossi" }));
    expect(request).toHaveBeenCalledWith("PUT", "/v1/users/giulia.rossi/block", { token: "tok" });
    expect(await screen.findByText("@giulia.rossi bloccato.")).toBeOnTheScreen();
    expect(router.back).toHaveBeenCalled();
  });
});

describe("Il proprio profilo", () => {
  test("richieste in attesa e contatori portano agli elenchi", async () => {
    get.mockImplementation((path: string) =>
      Promise.resolve(
        path.includes("/posts")
          ? { items: [], next_cursor: null, cover_id: null }
          : person({ nickname: "fra.fit", is_self: true, can_view_posts: true, pending_requests: 2 }),
      ),
    );
    const user = userEvent.setup();
    await render(<PortfolioScreen nickname="fra.fit" />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Richieste di follow: 2" }));
    expect(router.push).toHaveBeenCalledWith({ pathname: "/people", params: { tab: "requests" } });
    await user.press(screen.getByRole("link", { name: "80 seguiti" }));
    expect(router.push).toHaveBeenLastCalledWith({ pathname: "/people", params: { tab: "following" } });
    expect(screen.queryByRole("button", { name: "Segui" })).toBeNull();
    await user.press(screen.getByRole("button", { name: "Trova persone" }));
    expect(router.push).toHaveBeenLastCalledWith("/find");
  });
});

describe("Elenchi", () => {
  test("accetta una richiesta: sparisce subito", async () => {
    useLocalSearchParams.mockReturnValue({ tab: "requests" });
    let pending = ["marco_atelier", "ele.vintage"];
    get.mockImplementation(() => Promise.resolve(people(...pending)));
    request.mockImplementation(() => {
      pending = ["ele.vintage"];
      return Promise.resolve(undefined);
    });
    const user = userEvent.setup();
    await render(<PeopleScreen />, { wrapper: Providers });
    expect(await screen.findByText("@marco_atelier")).toBeOnTheScreen();
    expect(get).toHaveBeenCalledWith("/v1/me/follow-requests", expect.anything());
    await user.press(screen.getAllByRole("button", { name: "Accetta" })[0]!);
    expect(request).toHaveBeenCalledWith("POST", "/v1/me/follow-requests", {
      token: "tok",
      body: { nickname: "marco_atelier", decision: "accept" },
    });
    expect(await screen.findByText("@marco_atelier ora ti segue.")).toBeOnTheScreen();
    expect(screen.queryByText("@marco_atelier")).toBeNull();
  });

  test("rifiuto non riuscito: la richiesta torna", async () => {
    useLocalSearchParams.mockReturnValue({ tab: "requests" });
    get.mockResolvedValue(people("marco_atelier"));
    request.mockRejectedValue(new TypeError("Network request failed"));
    const user = userEvent.setup();
    await render(<PeopleScreen />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Rifiuta @marco_atelier" }));
    expect(await screen.findByText(/Controlla la connessione/)).toBeOnTheScreen();
    expect(screen.getByText("@marco_atelier")).toBeOnTheScreen();
  });

  test("follower, seguiti, bloccati", async () => {
    useLocalSearchParams.mockReturnValue({ tab: "followers" });
    get.mockImplementation((path: string) =>
      Promise.resolve(path.includes("blocks") ? people("disturbatore") : people("ele.vintage")),
    );
    request.mockResolvedValue(undefined);
    const user = userEvent.setup();
    await render(<PeopleScreen />, { wrapper: Providers });
    await user.press(await screen.findByRole("button", { name: "Rimuovi" }));
    expect(request).toHaveBeenCalledWith("DELETE", "/v1/me/followers/ele.vintage", { token: "tok" });

    await user.press(screen.getByRole("tab", { name: "Bloccati" }));
    await user.press(await screen.findByRole("button", { name: "Sblocca" }));
    expect(request).toHaveBeenLastCalledWith("DELETE", "/v1/users/disturbatore/block", { token: "tok" });
    expect(await screen.findByText("@disturbatore sbloccato.")).toBeOnTheScreen();
  });

  test("elenco vuoto", async () => {
    useLocalSearchParams.mockReturnValue({ tab: "following" });
    get.mockResolvedValue(people());
    await render(<PeopleScreen />, { wrapper: Providers });
    expect(await screen.findByText("Non segui nessuno")).toBeOnTheScreen();
  });
});

describe("Trova persone", () => {
  test("nickname esatto: scheda con Segui", async () => {
    get.mockResolvedValue(person());
    const user = userEvent.setup();
    await render(<FindScreen />, { wrapper: Providers });
    await user.type(screen.getByLabelText(/Nickname/i), "@Giulia.Rossi");
    await user.press(screen.getByRole("button", { name: "Cerca" }));
    expect(get).toHaveBeenCalledWith("/v1/users/giulia.rossi", expect.objectContaining({ token: "tok" }));
    expect(await screen.findByText(/PRIVATO · 4 fit · 120 follower/)).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Segui" })).toBeOnTheScreen();
    await user.press(screen.getByRole("link", { name: "Apri il profilo di @giulia.rossi" }));
    expect(router.push).toHaveBeenCalledWith({ pathname: "/user/[nickname]", params: { nickname: "giulia.rossi" } });
  });

  test("nessun profilo, e nickname non valido senza chiedere al server", async () => {
    get.mockRejectedValue(new ApiError(404, "user.not_found", "Profilo non trovato"));
    const user = userEvent.setup();
    await render(<FindScreen />, { wrapper: Providers });
    await user.type(screen.getByLabelText(/Nickname/i), "nessuno_qui");
    await user.press(screen.getByRole("button", { name: "Cerca" }));
    expect(await screen.findByText("Nessun profilo con questo nickname.")).toBeOnTheScreen();

    get.mockClear();
    await user.clear(screen.getByLabelText(/Nickname/i));
    await user.type(screen.getByLabelText(/Nickname/i), "no spazi");
    await user.press(screen.getByRole("button", { name: "Cerca" }));
    expect(screen.getByText("Questo non è un nickname valido.")).toBeOnTheScreen();
    expect(get).not.toHaveBeenCalled();
  });
});
