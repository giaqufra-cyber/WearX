import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { DataExport, Device } from "@wearx/api-types";
import { fireEvent, render, screen, userEvent, waitFor } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import ForgotScreen from "@/app/(auth)/forgot";
import ChangePasswordScreen from "@/app/change-password";
import DataExportScreen from "@/app/data-export";
import DeleteAccountScreen from "@/app/delete-account";
import DeletingScreen from "@/app/deleting";
import DevicesScreen from "@/app/devices";
import SettingsScreen from "@/app/settings";
import { checkPasswordLeak } from "@/features/auth/passwordLeak";
import { useRecovery } from "@/features/auth/recovery";
import { decideRoute } from "@/features/auth/routing";
import { formatBytes, lastSeen } from "@/features/privacy/api";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";
import { ToastProvider } from "@/ui/Toast";

jest.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      resetPasswordForEmail: jest.fn(),
      verifyOtp: jest.fn(),
      updateUser: jest.fn(),
      signOut: jest.fn(),
      signInWithPassword: jest.fn(),
      getSession: jest.fn(),
    },
  },
}));
jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: () => true },
  useLocalSearchParams: jest.fn(() => ({})),
}));
jest.mock("expo-linking", () => ({ createURL: (path: string) => `wearx://${path.replace(/^\//, "")}` }));
jest.mock("expo-web-browser", () => ({ openBrowserAsync: jest.fn() }));
jest.mock("@/lib/env", () => ({ env: { ...jest.requireActual("@/lib/env").env, emailOtp: true } }));
jest.mock("@/features/auth/passwordLeak", () => ({ checkPasswordLeak: jest.fn() }));
const mockSignOut = jest.fn();
const mockProfile = { nickname: "fra.fit", hide_prices: false, hide_vote_count: false, status: "active" };
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({
    session: { access_token: "tok", user: { id: "u1", email: "fra@example.com" } },
    profile: mockProfile,
    signOut: mockSignOut,
  }),
}));
jest.mock("@/lib/api", () => ({ ...jest.requireActual("@/lib/api"), apiGet: jest.fn(), apiRequest: jest.fn() }));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const { openBrowserAsync } = jest.requireMock("expo-web-browser") as { openBrowserAsync: jest.Mock };
const auth = supabase.auth as unknown as Record<string, jest.Mock>;
const get = apiGet as jest.Mock;
const request = apiRequest as jest.Mock;
const leak = checkPasswordLeak as jest.Mock;

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
    defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } },
  });
  request.mockResolvedValue(undefined);
  leak.mockResolvedValue("clean");
  auth.signOut!.mockResolvedValue({ error: null });
  auth.getSession!.mockResolvedValue({ data: { session: { access_token: "tok2" } } });
  useRecovery.getState().finish();
  env.emailOtp = true;
});
afterEach(() => client.clear());

const STRONG = "Trento-Monaco-2026!";

test("instradamento: account in cancellazione e recupero password", () => {
  expect(decideRoute({ initializing: false, hasSession: true, me: { state: "ok", status: "pending_deletion" } })).toBe(
    "deleting",
  );
  expect(
    decideRoute({ initializing: false, hasSession: true, recovering: true, me: { state: "ok", status: "active" } }),
  ).toBe("auth");
});

test("formati", () => {
  const now = new Date("2026-10-05T12:00:00Z");
  expect(lastSeen("2026-10-05T11:59:50Z", now)).toBe("attivo adesso");
  expect(lastSeen("2026-10-05T11:50:00Z", now)).toBe("attivo 10 min fa");
  expect(lastSeen("2026-10-04T10:00:00Z", now)).toBe("attivo ieri");
  expect(lastSeen("2026-09-01T10:00:00Z", now)).toMatch(/^attivo il 1 set/);
  expect(formatBytes(2_400_000)).toBe("2,3 MB");
  expect(formatBytes(300)).toBe("1 KB");
});

test("impostazioni: interruttori e voci", async () => {
  request.mockResolvedValue({ ...mockProfile, hide_prices: true });
  const user = userEvent.setup();
  await render(<SettingsScreen />, { wrapper: Providers });
  await user.press(screen.getByRole("switch", { name: "Nascondi i prezzi" }));
  expect(request).toHaveBeenCalledWith("PATCH", "/v1/me", { token: "tok", body: { hide_prices: true } });
  await user.press(screen.getByRole("button", { name: /^Dispositivi collegati/ }));
  expect(router.push).toHaveBeenCalledWith("/devices");
  await user.press(screen.getByRole("button", { name: /^Cancella l'account/ }));
  expect(router.push).toHaveBeenCalledWith("/delete-account");
  await user.press(screen.getByRole("button", { name: "Esci" }));
  expect(mockSignOut).toHaveBeenCalled();
});

const device = (extra: Partial<Device>): Device => ({
  id: "s1",
  label: "iPhone 15",
  platform: "ios",
  app_version: "0.1.0",
  created_at: "2026-10-01T10:00:00Z",
  last_seen: new Date().toISOString(),
  current: true,
  ...extra,
});

test("dispositivi: questo, gli altri, uscire con conferma", async () => {
  get.mockResolvedValue([device({}), device({ id: "s2", label: "Pixel 8", platform: "android", current: false })]);
  const user = userEvent.setup();
  await render(<DevicesScreen />, { wrapper: Providers });
  expect(await screen.findByText("iPhone 15")).toBeOnTheScreen();
  expect(screen.getByText("QUI")).toBeOnTheScreen();
  expect(screen.getByText(/Android · app 0.1.0 · attivo adesso/)).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Esci" }));
  expect(screen.getByText("Uscire da Pixel 8?")).toBeOnTheScreen();
  expect(request).not.toHaveBeenCalled();
  const buttons = screen.getAllByRole("button", { name: "Esci" });
  await user.press(buttons[buttons.length - 1]!);
  expect(request).toHaveBeenCalledWith("DELETE", "/v1/me/devices/s2", { token: "tok" });

  await user.press(screen.getByRole("button", { name: "Esci da tutti gli altri dispositivi" }));
  const confirm = screen.getAllByRole("button", { name: "Esci" });
  await user.press(confirm[confirm.length - 1]!);
  await waitFor(() => expect(auth.signOut).toHaveBeenCalledWith({ scope: "others" }));
  expect(request).toHaveBeenCalledWith("POST", "/v1/me/devices/revoke-others", { token: "tok2" });
});

const exportOf = (extra: Partial<DataExport>): DataExport => ({
  id: "e1",
  status: "pending",
  created_at: "2026-10-05T10:00:00Z",
  ready_at: null,
  expires_at: null,
  size_bytes: null,
  url: null,
  ...extra,
});

test("archivio: chiedi, in preparazione, pronto da scaricare", async () => {
  get.mockResolvedValueOnce(null);
  request.mockResolvedValue(exportOf({}));
  const user = userEvent.setup();
  await render(<DataExportScreen />, { wrapper: Providers });
  await user.press(await screen.findByRole("button", { name: "Prepara l'archivio" }));
  expect(request).toHaveBeenCalledWith("POST", "/v1/me/export", { token: "tok" });
  expect(await screen.findByText("Stiamo preparando il tuo archivio")).toBeOnTheScreen();

  client.setQueryData(
    ["privacy", "u1", "export"],
    exportOf({ status: "ready", url: "https://store/x.zip", size_bytes: 2_400_000, expires_at: "2026-10-12T10:00:00Z" }),
  );
  await user.press(await screen.findByRole("button", { name: "Scarica l'archivio" }));
  expect(openBrowserAsync).toHaveBeenCalledWith("https://store/x.zip");
  expect(screen.getByText(/2,3 MB · scaricabile fino al 12 ottobre 2026/)).toBeOnTheScreen();
});

test("archivio: una volta al giorno", async () => {
  get.mockResolvedValue(exportOf({ status: "expired" }));
  request.mockRejectedValue(new ApiError(429, "export.too_soon", "domani"));
  const user = userEvent.setup();
  await render(<DataExportScreen />, { wrapper: Providers });
  await user.press(await screen.findByRole("button", { name: "Prepara l'archivio" }));
  expect(await screen.findByText("Puoi chiedere un nuovo archivio una volta al giorno.")).toBeOnTheScreen();
});

test("cancellazione: serve il nickname, poi la richiesta", async () => {
  request.mockResolvedValue({ delete_after: "2026-11-04T10:00:00Z" });
  const user = userEvent.setup();
  await render(<DeleteAccountScreen />, { wrapper: Providers });
  const go = screen.getByRole("button", { name: "Cancella il mio account" });
  expect(go).toBeDisabled();
  await fireEvent.changeText(screen.getByLabelText(/PER CONFERMARE/), "@Fra.Fit");
  expect(go).toBeEnabled();
  await user.press(go);
  expect(request).toHaveBeenCalledWith("POST", "/v1/me/deletion", { token: "tok", body: { nickname: "@Fra.Fit" } });
});

test("account in cancellazione: data e annulla", async () => {
  get.mockResolvedValue({ pending: true, delete_after: "2026-11-04T10:00:00Z" });
  const user = userEvent.setup();
  await render(<DeletingScreen />, { wrapper: Providers });
  expect(await screen.findByText(/cancellato per sempre il 4 novembre 2026/)).toBeOnTheScreen();
  await user.press(screen.getByRole("button", { name: "Annulla la cancellazione" }));
  expect(request).toHaveBeenCalledWith("DELETE", "/v1/me/deletion", { token: "tok" });
});

describe("Password", () => {
  test("dimenticata: stessa risposta per tutti, codice, nuova password, fuori dagli altri dispositivi", async () => {
    auth.resetPasswordForEmail!.mockResolvedValue({ error: null });
    auth.verifyOtp!.mockResolvedValue({ error: null });
    auth.updateUser!.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    await render(<ForgotScreen />, { wrapper: Providers });
    await fireEvent.changeText(screen.getByLabelText("EMAIL"), " Fra@Example.com ");
    await user.press(screen.getByRole("button", { name: "Mandami il codice" }));
    expect(auth.resetPasswordForEmail).toHaveBeenCalledWith("fra@example.com", { redirectTo: "wearx://reset-password" });
    expect(screen.getByText(/è registrata, ti è arrivata una mail/)).toBeOnTheScreen();

    await fireEvent.changeText(screen.getByLabelText("CODICE"), "123456");
    await waitFor(() =>
      expect(auth.verifyOtp).toHaveBeenCalledWith({ email: "fra@example.com", token: "123456", type: "recovery" }),
    );
    expect(useRecovery.getState().recovering).toBe(true); // resta sulle schermate di accesso
    await fireEvent.changeText(await screen.findByLabelText("NUOVA PASSWORD"), STRONG);
    await fireEvent.changeText(screen.getByLabelText("RIPETI LA PASSWORD"), STRONG);
    await user.press(screen.getByRole("button", { name: "Salva ed entra" }));
    await waitFor(() => expect(auth.updateUser).toHaveBeenCalledWith({ password: STRONG }));
    expect(auth.signOut).toHaveBeenCalledWith({ scope: "others" });
    expect(useRecovery.getState().recovering).toBe(false);
  });

  test("codice sbagliato: si riprova, si resta fuori", async () => {
    auth.resetPasswordForEmail!.mockResolvedValue({ error: null });
    auth.verifyOtp!.mockResolvedValue({ error: { code: "otp_expired" } });
    await render(<ForgotScreen />, { wrapper: Providers });
    await fireEvent.changeText(screen.getByLabelText("EMAIL"), "fra@example.com");
    await userEvent.setup().press(screen.getByRole("button", { name: "Mandami il codice" }));
    await fireEvent.changeText(screen.getByLabelText("CODICE"), "000000");
    expect(await screen.findByText("Il codice è scaduto o non è corretto. Chiedine uno nuovo.")).toBeOnTheScreen();
    expect(useRecovery.getState().recovering).toBe(false);
  });

  test("cambio: password attuale verificata, password violata rifiutata", async () => {
    auth.signInWithPassword!.mockResolvedValueOnce({ error: { code: "invalid_credentials" } });
    const user = userEvent.setup();
    await render(<ChangePasswordScreen />, { wrapper: Providers });
    const save = screen.getByRole("button", { name: "Salva la nuova password" });
    await fireEvent.changeText(screen.getByLabelText("NUOVA PASSWORD"), STRONG);
    await fireEvent.changeText(screen.getByLabelText("RIPETI LA PASSWORD"), STRONG);
    expect(save).toBeDisabled(); // manca la password attuale
    await fireEvent.changeText(screen.getByLabelText("PASSWORD ATTUALE"), "sbagliata");
    await user.press(save);
    expect(await screen.findByText("La password attuale non è corretta.")).toBeOnTheScreen();
    expect(auth.updateUser).not.toHaveBeenCalled();

    leak.mockResolvedValueOnce("compromised");
    await user.press(save);
    expect(await screen.findByText(/violazione di dati/)).toBeOnTheScreen();

    auth.signInWithPassword!.mockResolvedValue({ error: null });
    auth.updateUser!.mockResolvedValue({ error: null });
    await user.press(save);
    await waitFor(() => expect(auth.updateUser).toHaveBeenCalledWith({ password: STRONG }));
    expect(auth.signInWithPassword).toHaveBeenLastCalledWith({ email: "fra@example.com", password: "sbagliata" });
    expect(router.back).toHaveBeenCalled();
  });

  test("le due password devono coincidere", async () => {
    await render(<ChangePasswordScreen />, { wrapper: Providers });
    await fireEvent.changeText(screen.getByLabelText("NUOVA PASSWORD"), STRONG);
    await fireEvent.changeText(screen.getByLabelText("RIPETI LA PASSWORD"), `${STRONG}x`);
    expect(screen.getByText("Le due password non coincidono.")).toBeOnTheScreen();
  });
});
