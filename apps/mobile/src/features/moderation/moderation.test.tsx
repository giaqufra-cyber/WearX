import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ModerationNotice, Post } from "@wearx/api-types";
import { render, screen, userEvent } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import SuspendedScreen from "@/app/suspended";
import { PostCard } from "@/features/feed/PostCard";
import { reviewLabel } from "@/features/moderation/api";
import { NoticeList } from "@/features/moderation/NoticeList";
import { ReportSheet } from "@/features/moderation/ReportSheet";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), navigate: jest.fn(), canGoBack: () => true },
}));
const mockSignOut = jest.fn();
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({ session: { access_token: "tok", user: { id: "u1" } }, signOut: mockSignOut }),
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
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });
});
afterEach(() => client.clear());

const notice = (extra: Partial<ModerationNotice> = {}): ModerationNotice => ({
  id: "a1",
  action: "hide",
  target_type: "post",
  reason: "nudità o contenuti sessuali",
  statement: "Il tuo fit «Serata» è stato nascosto. Se pensi che sia un errore puoi fare reclamo.",
  automated: false,
  created_at: "2026-10-05T08:00:00Z",
  expires_at: null,
  post_id: "p1",
  appeal: null,
  can_appeal: true,
  appeal_until: "2027-04-06T08:00:00Z",
  ...extra,
});

test("tempi di revisione", () => {
  expect(reviewLabel(1)).toBe("entro 1 ora");
  expect(reviewLabel(72)).toBe("entro 72 ore");
});

describe("Segnala", () => {
  test("motivo, dettagli, conferma con i tempi", async () => {
    request.mockResolvedValue({ id: "r1", priority: 2, review_within_hours: 72 });
    const user = userEvent.setup();
    await render(<ReportSheet target={{ type: "post", id: "p9" }} visible onClose={jest.fn()} />, { wrapper: Providers });
    expect(screen.getByRole("button", { name: "Invia segnalazione" })).toBeDisabled();
    await user.press(screen.getByRole("radio", { name: "Spam" }));
    await user.type(screen.getByLabelText(/Dettagli/), "  link ovunque ");
    await user.press(screen.getByRole("button", { name: "Invia segnalazione" }));
    expect(request).toHaveBeenCalledWith("POST", "/v1/reports", {
      token: "tok",
      body: { target_type: "post", target_id: "p9", reason: "spam", details: "link ovunque" },
    });
    expect(await screen.findByText(/una persona la controlla entro 72 ore/)).toBeOnTheScreen();
    expect(screen.queryByText(/112/)).toBeNull();
  });

  test("minore in pericolo: in più il 112", async () => {
    request.mockResolvedValue({ id: "r1", priority: 0, review_within_hours: 1 });
    const user = userEvent.setup();
    await render(<ReportSheet target={{ type: "profile", nickname: "x.y" }} visible onClose={jest.fn()} />, {
      wrapper: Providers,
    });
    expect(screen.getByText("Segnala @x.y")).toBeOnTheScreen();
    await user.press(screen.getByRole("radio", { name: "Un minore è in pericolo" }));
    await user.press(screen.getByRole("button", { name: "Invia segnalazione" }));
    expect(request).toHaveBeenCalledWith("POST", "/v1/reports", {
      token: "tok",
      body: { target_type: "profile", nickname: "x.y", reason: "minor_safety" },
    });
    expect(await screen.findByText(/entro 1 ora/)).toBeOnTheScreen();
    expect(screen.getByText("Se qualcuno è in pericolo adesso, chiama il 112.")).toBeOnTheScreen();
  });

  test("errore spiegato", async () => {
    request.mockRejectedValue(new ApiError(429, "rate.limited", "Troppe"));
    const user = userEvent.setup();
    await render(<ReportSheet target={{ type: "post", id: "p9" }} visible onClose={jest.fn()} />, { wrapper: Providers });
    await user.press(screen.getByRole("radio", { name: "Altro" }));
    await user.press(screen.getByRole("button", { name: "Invia segnalazione" }));
    expect(await screen.findByText("Hai inviato molte segnalazioni oggi: riprova domani.")).toBeOnTheScreen();
  });

  test("sul fit altrui c'è Segnala, sul proprio no", async () => {
    const post: Post = {
      id: "p1",
      status: "active",
      style: { slug: "gala", name: "Galà", tone: "#3A1418" },
      author: null,
      is_own: false,
      caption: null,
      media: [],
      items: [],
      published_at: null,
      created_at: "2026-10-05T08:00:00Z",
      vote: { mine: null, my_style_confirm: null, average: null, vote_count: null, style_match: null, ask_style_confirm: false },
    };
    const user = userEvent.setup();
    const { rerender } = await render(<PostCard post={post} width={390} onVote={jest.fn()} voting={false} />, {
      wrapper: Providers,
    });
    await user.press(screen.getByRole("button", { name: "Segnala il fit" }));
    expect(screen.getByText("Segnala il fit")).toBeOnTheScreen();
    await rerender(<PostCard post={{ ...post, is_own: true }} width={390} onVote={jest.fn()} voting={false} />);
    expect(screen.queryByRole("button", { name: "Segnala il fit" })).toBeNull();
  });
});

describe("Avvisi e reclami", () => {
  test("avviso con motivo, apri il fit, reclamo", async () => {
    let appealed = false;
    get.mockImplementation(() =>
      Promise.resolve([
        appealed
          ? notice({ can_appeal: false, appeal: { status: "open", created_at: "x", decided_at: null, decision_note: null } })
          : notice(),
        notice({ id: "a0", action: "restore", reason: "il tuo reclamo è stato accolto", statement: "Annullata.", can_appeal: false, post_id: null }),
      ]),
    );
    request.mockImplementation(() => {
      appealed = true;
      return Promise.resolve({ status: "open", created_at: "x", decided_at: null, decision_note: null });
    });
    const user = userEvent.setup();
    await render(<NoticeList />, { wrapper: Providers });

    expect(await screen.findByText("Fit nascosto")).toBeOnTheScreen();
    expect(screen.getByText(/DECISIONE DI UN MODERATORE · NUDITÀ/)).toBeOnTheScreen();
    expect(screen.getByText("Decisione annullata")).toBeOnTheScreen();
    expect(screen.getAllByRole("button", { name: "Fai reclamo" })).toHaveLength(1);

    await user.press(screen.getByRole("button", { name: "Apri il fit" }));
    expect(router.push).toHaveBeenCalledWith({ pathname: "/post/[id]", params: { id: "p1" } });

    await user.press(screen.getByRole("button", { name: "Fai reclamo" }));
    expect(screen.getByText("Lo legge un moderatore diverso da chi ha deciso.")).toBeOnTheScreen();
    await user.type(screen.getByLabelText(/Il tuo reclamo/), "È un costume da bagno.");
    await user.press(screen.getByRole("button", { name: "Invia reclamo" }));
    expect(request).toHaveBeenCalledWith("POST", "/v1/me/moderation/a1/appeal", {
      token: "tok",
      body: { text: "È un costume da bagno." },
    });
    expect(await screen.findByText("Reclamo in esame")).toBeOnTheScreen();
    expect(screen.queryByRole("button", { name: "Fai reclamo" })).toBeNull();
  });

  test("reclamo deciso: esito e nota del moderatore", async () => {
    get.mockResolvedValue([
      notice({
        can_appeal: false,
        appeal: { status: "upheld", created_at: "x", decided_at: "y", decision_note: "La foto viola le regole." },
      }),
    ]);
    await render(<NoticeList />, { wrapper: Providers });
    expect(await screen.findByText("Reclamo respinto")).toBeOnTheScreen();
    expect(screen.getByText("La foto viola le regole.")).toBeOnTheScreen();
  });

  test("nessun avviso", async () => {
    get.mockResolvedValue([]);
    await render(<NoticeList />, { wrapper: Providers });
    expect(await screen.findByText("Nessun avviso")).toBeOnTheScreen();
  });

  test("account sospeso: motivo e reclamo senza entrare nell'app", async () => {
    get.mockResolvedValue([notice({ action: "suspend", reason: "sicurezza dei minori", post_id: null })]);
    const user = userEvent.setup();
    await render(<SuspendedScreen />, { wrapper: Providers });
    expect(await screen.findByRole("button", { name: "Fai reclamo" })).toBeOnTheScreen();
    expect(screen.getByText(/SICUREZZA DEI MINORI/)).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Esci" }));
    expect(mockSignOut).toHaveBeenCalled();
  });
});
