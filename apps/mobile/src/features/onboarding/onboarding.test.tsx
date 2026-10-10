import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { AgeStatus, AppConfig } from "@wearx/api-types";
import { fireEvent, render, screen, userEvent } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import AgeScreen from "@/app/(onboarding)/age";
import AgeWaitScreen from "@/app/(onboarding)/age-wait";
import PickStylesScreen from "@/app/(onboarding)/pick-styles";
import ProfileTypeScreen from "@/app/(onboarding)/profile-type";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { useNicknameAvailability } from "@/features/auth/useNicknameAvailability";
import { createProfile, isoDate, startAgeSession, useAgeStatus } from "@/features/onboarding/api";
import { useAppConfig } from "@/features/styles/useAppConfig";
import { ApiError } from "@/lib/api";
import { ToastProvider } from "@/ui/Toast";

jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: () => true },
}));
jest.mock("expo-web-browser", () => ({ openAuthSessionAsync: jest.fn(async () => ({ type: "success" })) }));
jest.mock("@/features/auth/AuthProvider", () => ({
  ME_QUERY_KEY: ["me"],
  useAuth: () => ({
    session: { access_token: "tok", user: { id: "u1", user_metadata: { nickname: "fra.dal.meta" } } },
    signOut: jest.fn(),
  }),
}));
jest.mock("@/features/onboarding/api", () => ({
  ...jest.requireActual("@/features/onboarding/api"),
  useAgeStatus: jest.fn(),
  startAgeSession: jest.fn(),
  createProfile: jest.fn(),
  ageReturnUrl: () => "wearx://age-wait",
}));
jest.mock("@/features/styles/useAppConfig", () => ({ useAppConfig: jest.fn() }));
jest.mock("@/features/auth/useNicknameAvailability", () => ({ useNicknameAvailability: jest.fn() }));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const WebBrowser = jest.requireMock("expo-web-browser") as { openAuthSessionAsync: jest.Mock };
const ageStatus = useAgeStatus as jest.Mock;
const start = startAgeSession as jest.Mock;
const create = createProfile as jest.Mock;
const appConfig = useAppConfig as jest.Mock;

const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 47, left: 0, right: 0, bottom: 34 } };
let queryClient: QueryClient;
function Providers({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <SafeAreaProvider initialMetrics={metrics}>
        <ToastProvider>{children}</ToastProvider>
      </SafeAreaProvider>
    </QueryClientProvider>
  );
}

function status(data: Partial<AgeStatus>, extra: Record<string, unknown> = {}) {
  ageStatus.mockReturnValue({
    isPending: false,
    isError: false,
    isFetchedAfterMount: true,
    refetch: jest.fn(),
    data: { verified: false, age_band: null, methods: ["selfie_estimation", "id_document"], latest: null, ...data },
    ...extra,
  });
}

const style = (slug: string, name: string, min_age_band = "16_plus") => ({
  slug,
  name,
  tagline: `${name} tagline`,
  tone: "#2A2A2E",
  min_age_band,
  seasonal: false,
  active_until: null,
  category: "stili",
});

const config: AppConfig = {
  min_app_version: "0.1.0",
  store: { ios: null, android: null },
  attestation: { mode: "off", android_project_number: null },
  terms_version: "2026-10",
  feature_flags: { business_accounts: false },
  styles: [style("old-money", "Old Money"), style("jappo", "Jappo"), style("beach-party", "Beach Party", "18_plus")],
  legal: { terms: "", privacy: "", community_rules: "", feed_explainer: "" },
};

beforeEach(() => {
  jest.clearAllMocks();
  queryClient = new QueryClient();
  useSignupDraft.getState().clear();
  appConfig.mockReturnValue({ isPending: false, isError: false, data: config, refetch: jest.fn() });
  (useNicknameAvailability as jest.Mock).mockReturnValue("available");
});

describe("Verifica dell'età", () => {
  test("con la data dalla registrazione: avvia, apre il fornitore, passa all'attesa", async () => {
    useSignupDraft.getState().set({ birth: { day: 14, month: 3, year: 2003 } });
    status({});
    start.mockResolvedValue({ id: "v1", method: "selfie_estimation", status: "pending", redirect_url: "https://fornitore/x" });
    const user = userEvent.setup();
    await render(<AgeScreen />, { wrapper: Providers });

    expect(screen.getByText("Stima con selfie")).toBeOnTheScreen();
    expect(screen.getByText("Documento d'identità")).toBeOnTheScreen();
    expect(screen.queryByText("SPID")).toBeNull();

    await user.press(screen.getByRole("button", { name: /Stima con selfie/ }));
    expect(start).toHaveBeenCalledWith("tok", "selfie_estimation", "2003-03-14");
    expect(WebBrowser.openAuthSessionAsync).toHaveBeenCalledWith("https://fornitore/x", "wearx://age-wait");
    expect(router.push).toHaveBeenCalledWith("/age-wait");
  });

  test("app riaperta: la data va reinserita, sotto i 16 i metodi restano bloccati", async () => {
    status({});
    await render(<AgeScreen />, { wrapper: Providers });
    const selfie = screen.getByRole("button", { name: /Stima con selfie/ });
    expect(selfie).toBeDisabled();

    await fireEvent.changeText(screen.getByLabelText("GIORNO"), "1");
    await fireEvent.changeText(screen.getByLabelText("MESE"), "1");
    await fireEvent.changeText(screen.getByLabelText("ANNO"), String(new Date().getFullYear() - 12));
    expect(screen.getByText("WearX è riservata a chi ha almeno 16 anni.")).toBeOnTheScreen();
    expect(selfie).toBeDisabled();

    await fireEvent.changeText(screen.getByLabelText("ANNO"), "2000");
    expect(selfie).toBeEnabled();
  });

  test("dopo una stima insufficiente propone prima il documento", async () => {
    useSignupDraft.getState().set({ birth: { day: 14, month: 3, year: 2003 } });
    status({ latest: { id: "v1", method: "selfie_estimation", status: "failed", failure_reason: "inconsistent" } });
    await render(<AgeScreen />, { wrapper: Providers });
    expect(screen.getByText(/Usa un documento per completare/)).toBeOnTheScreen();
    const order = screen
      .getAllByText(/^(Documento d'identità|Stima con selfie)$/)
      .map((node) => String(node.props.children));
    expect(order).toEqual(["Documento d'identità", "Stima con selfie"]);
    expect(screen.queryByText("RAPIDO")).toBeNull();
  });

  test("sotto i 16 da documento: schermata di blocco", async () => {
    status({ latest: { id: "v1", method: "id_document", status: "failed", failure_reason: "underage" } });
    await render(<AgeScreen />, { wrapper: Providers });
    expect(screen.getByText("WearX è per chi ha 16 anni o più")).toBeOnTheScreen();
    expect(screen.queryByText("Stima con selfie")).toBeNull();
  });

  test("blocco segnalato dal server all'avvio", async () => {
    useSignupDraft.getState().set({ birth: { day: 14, month: 3, year: 2003 } });
    status({});
    start.mockRejectedValue(new ApiError(403, "age.blocked", "Bloccato"));
    const user = userEvent.setup();
    await render(<AgeScreen />, { wrapper: Providers });
    await user.press(screen.getByRole("button", { name: /Documento d'identità/ }));
    expect(screen.getByText("WearX è per chi ha 16 anni o più")).toBeOnTheScreen();
  });

  test("già verificata: si passa al tipo di profilo", async () => {
    status({ verified: true, age_band: "18_plus" });
    await render(<AgeScreen />, { wrapper: Providers });
    expect(router.replace).toHaveBeenCalledWith("/profile-type");
  });
});

describe("Attesa dell'esito", () => {
  test("esito positivo letto dopo l'apertura: avanti", async () => {
    status({ verified: true, age_band: "16_17" });
    await render(<AgeWaitScreen />, { wrapper: Providers });
    expect(router.replace).toHaveBeenCalledWith("/profile-type");
  });

  test("ignora l'esito in cache del tentativo precedente", async () => {
    status(
      { latest: { id: "v0", method: "selfie_estimation", status: "failed", failure_reason: "not_completed" } },
      { isFetchedAfterMount: false },
    );
    await render(<AgeWaitScreen />, { wrapper: Providers });
    expect(router.replace).not.toHaveBeenCalled();
    expect(screen.getByText("Aspettiamo l'esito della verifica…")).toBeOnTheScreen();
  });

  test("esito negativo: si torna ai metodi", async () => {
    status({ latest: { id: "v1", method: "selfie_estimation", status: "failed", failure_reason: "inconsistent" } });
    await render(<AgeWaitScreen />, { wrapper: Providers });
    expect(router.replace).toHaveBeenCalledWith("/age");
  });
});

describe("Tipo di profilo", () => {
  test("16-17 anni: Business non selezionabile; si prosegue con Privato", async () => {
    status({ verified: true, age_band: "16_17" });
    appConfig.mockReturnValue({ isPending: false, isError: false, data: { ...config, feature_flags: { business_accounts: true } } });
    const user = userEvent.setup();
    await render(<ProfileTypeScreen />, { wrapper: Providers });
    expect(screen.getByRole("radio", { name: /Business/ })).toBeDisabled();
    expect(screen.getByText("Il profilo Business è solo per maggiorenni.")).toBeOnTheScreen();
    await user.press(screen.getByRole("button", { name: "Continua" }));
    expect(useSignupDraft.getState().accountType).toBe("private");
    expect(router.push).toHaveBeenCalledWith("/pick-styles");
  });

  test("maggiorenne con Business attivo: si può scegliere", async () => {
    status({ verified: true, age_band: "18_plus" });
    appConfig.mockReturnValue({ isPending: false, isError: false, data: { ...config, feature_flags: { business_accounts: true } } });
    const user = userEvent.setup();
    await render(<ProfileTypeScreen />, { wrapper: Providers });
    await user.press(screen.getByRole("radio", { name: /Business/ }));
    expect(screen.getByRole("radio", { name: /Business/ })).toBeChecked();
    await user.press(screen.getByRole("button", { name: "Continua" }));
    expect(useSignupDraft.getState().accountType).toBe("business");
  });
});

describe("Scelta degli stili e creazione del profilo", () => {
  test("i 16-17enni non vedono gli stili 18+; crea il profilo e libera la bozza", async () => {
    status({ verified: true, age_band: "16_17" });
    useSignupDraft.getState().set({ nickname: "francesco", birth: { day: 1, month: 1, year: 2009 } });
    create.mockResolvedValue({ nickname: "francesco" });
    const user = userEvent.setup();
    await render(<PickStylesScreen />, { wrapper: Providers });

    expect(screen.queryByText("Beach Party")).toBeNull();
    const enter = screen.getByRole("button", { name: "Entra in WearX" });
    expect(enter).toBeDisabled();

    await user.press(screen.getByRole("checkbox", { name: /Old Money/ }));
    await user.press(screen.getByRole("checkbox", { name: /Jappo/ }));
    expect(screen.getByText("2 STILI")).toBeOnTheScreen();
    await user.press(enter);

    expect(create).toHaveBeenCalledWith("tok", {
      nickname: "francesco",
      terms_version: "2026-10",
      accept_community_rules: true,
      styles: ["old-money", "jappo"],
      account_type: "private",
    });
    expect(useSignupDraft.getState().birth).toBeNull();
    expect(screen.getByText("Benvenuto su WearX, @francesco.")).toBeOnTheScreen();
  });

  test("i maggiorenni vedono anche gli stili 18+", async () => {
    status({ verified: true, age_band: "18_plus" });
    await render(<PickStylesScreen />, { wrapper: Providers });
    expect(screen.getByText("Beach Party")).toBeOnTheScreen();
    expect(screen.getByText("18+")).toBeOnTheScreen();
  });

  test("app riaperta: nickname dai metadati; se nel frattempo è preso si sceglie un altro", async () => {
    status({ verified: true, age_band: "18_plus" });
    create.mockRejectedValueOnce(new ApiError(409, "nickname.taken", "Preso"));
    const user = userEvent.setup();
    await render(<PickStylesScreen />, { wrapper: Providers });
    expect(screen.queryByLabelText("NICKNAME")).toBeNull();

    await user.press(screen.getByRole("checkbox", { name: /Jappo/ }));
    await user.press(screen.getByRole("button", { name: "Entra in WearX" }));
    expect(create.mock.calls[0]?.[1]).toMatchObject({ nickname: "fra.dal.meta" });
    expect(screen.getByText(/qualcuno ha preso questo nickname/)).toBeOnTheScreen();

    create.mockResolvedValueOnce({ nickname: "fra.nuovo" });
    await fireEvent.changeText(screen.getByLabelText("NICKNAME"), "Fra.Nuovo");
    await user.press(screen.getByRole("button", { name: "Entra in WearX" }));
    expect(create.mock.calls[1]?.[1]).toMatchObject({ nickname: "fra.nuovo" });
  });
});

test("data ISO per l'API", () => {
  expect(isoDate({ day: 4, month: 3, year: 2003 })).toBe("2003-03-04");
});
