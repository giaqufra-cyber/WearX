import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { StyleProposal } from "@wearx/api-types";
import { fireEvent, render, screen, userEvent, waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import StyleProposalsScreen from "@/app/style-proposals";
import { progress } from "@/features/styles/proposals";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: () => true },
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

const proposal = (extra: Partial<StyleProposal> = {}): StyleProposal => ({
  id: "p1",
  name: "Avant-garde",
  tagline: "Silhouette estreme",
  category: "stili",
  supports: 24,
  threshold: 25,
  supported: false,
  mine: false,
  status: "open",
  style: null,
  created_at: "2026-10-11T10:00:00Z",
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
  useLocalSearchParams.mockReturnValue({});
  client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false, gcTime: Infinity } },
  });
  get.mockResolvedValue({ items: [proposal()], threshold: 25 });
});
afterEach(() => client.clear());

test("barra di avanzamento", () => {
  expect(progress({ supports: 12, threshold: 25 })).toEqual({ label: "12 su 25", ratio: 0.48 });
  expect(progress({ supports: 30, threshold: 25 }).ratio).toBe(1);
});

test("lo voglio: alla soglia lo stile nasce e si apre", async () => {
  request.mockResolvedValue(proposal({ supports: 25, supported: true, status: "approved", style: "avant-garde" }));
  const user = userEvent.setup();
  await render(<StyleProposalsScreen />, { wrapper: Providers });
  expect(await screen.findByText("Avant-garde")).toBeOnTheScreen();
  expect(screen.getByText("24 su 25")).toBeOnTheScreen();
  expect(screen.getByText("A 25 richieste diventa uno stile.")).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Lo voglio" }));
  expect(request).toHaveBeenCalledWith("PUT", "/v1/style-proposals/p1/support", { token: "tok" });
  expect(await screen.findByText("«Avant-garde» ora è uno stile. Ci sei dentro.")).toBeOnTheScreen();
  expect(router.push).toHaveBeenCalledWith({ pathname: "/style/[slug]", params: { slug: "avant-garde" } });
});

test("ritirare la richiesta", async () => {
  get.mockResolvedValue({ items: [proposal({ supported: true })], threshold: 25 });
  request.mockResolvedValue(proposal({ supports: 23 }));
  const user = userEvent.setup();
  await render(<StyleProposalsScreen />, { wrapper: Providers });
  await user.press(await screen.findByRole("button", { name: "Lo vuoi" }));
  expect(request).toHaveBeenCalledWith("DELETE", "/v1/style-proposals/p1/support", { token: "tok" });
});

test("proporre: nome dalla ricerca, categoria obbligatoria", async () => {
  useLocalSearchParams.mockReturnValue({ name: "Avant" });
  request.mockResolvedValue({ created: true, proposal: proposal({ id: "p2", name: "Avant", supports: 1 }) });
  const user = userEvent.setup();
  await render(<StyleProposalsScreen />, { wrapper: Providers });
  expect(await screen.findByLabelText("Nome dello stile")).toHaveDisplayValue("Avant");
  const send = screen.getByRole("button", { name: "Proponi" });
  expect(send).toBeDisabled();
  await user.press(screen.getByRole("radio", { name: "Sottoculture" }));
  await fireEvent.changeText(screen.getByLabelText("Descrizione dello stile"), "Nero, volumi");
  await user.press(send);
  expect(request).toHaveBeenCalledWith("POST", "/v1/style-proposals", {
    token: "tok",
    body: { name: "Avant", category: "sottoculture", tagline: "Nero, volumi" },
  });
  expect(await screen.findByText("Proposta inviata: servono 25 richieste.")).toBeOnTheScreen();
});

test("proporre uno stile che c'è già: si apre quello", async () => {
  request.mockRejectedValue(new ApiError(409, "style.exists", "x", undefined, { code: "style.exists", slug: "gala" }));
  const user = userEvent.setup();
  await render(<StyleProposalsScreen />, { wrapper: Providers });
  await user.press(await screen.findByRole("button", { name: "Proponi uno stile" }));
  await fireEvent.changeText(screen.getByLabelText("Nome dello stile"), "Galà");
  await user.press(screen.getByRole("radio", { name: "Occasioni" }));
  await user.press(screen.getByRole("button", { name: "Proponi" }));
  expect(await screen.findByText("Questo stile c'è già.")).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Apri lo stile" }));
  await waitFor(() => expect(router.push).toHaveBeenCalledWith({ pathname: "/style/[slug]", params: { slug: "gala" } }));
});
