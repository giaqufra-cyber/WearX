import { act, fireEvent, render, screen, userEvent } from "@testing-library/react-native";
import type { ReactNode } from "react";
import { SafeAreaProvider } from "react-native-safe-area-context";

import LoginScreen from "@/app/(auth)/login";
import SignupScreen from "@/app/(auth)/signup";
import VerifyScreen from "@/app/(auth)/verify";
import { checkPasswordLeak } from "@/features/auth/passwordLeak";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { useNicknameAvailability } from "@/features/auth/useNicknameAvailability";
import { supabase } from "@/lib/supabase";
import { ToastProvider } from "@/ui/Toast";

jest.mock("@/lib/supabase", () => ({
  supabase: {
    auth: { signUp: jest.fn(), verifyOtp: jest.fn(), resend: jest.fn(), signInWithPassword: jest.fn() },
  },
}));
jest.mock("expo-router", () => ({
  router: { push: jest.fn(), replace: jest.fn(), back: jest.fn(), canGoBack: () => false },
}));
jest.mock("@/features/auth/passwordLeak", () => ({ checkPasswordLeak: jest.fn() }));
jest.mock("@/features/auth/useNicknameAvailability", () => ({ useNicknameAvailability: jest.fn() }));

const { router } = jest.requireMock("expo-router") as { router: Record<string, jest.Mock> };
const auth = supabase.auth as unknown as Record<string, jest.Mock>;
const leak = checkPasswordLeak as jest.Mock;
const availability = useNicknameAvailability as jest.Mock;

const metrics = { frame: { x: 0, y: 0, width: 390, height: 844 }, insets: { top: 47, left: 0, right: 0, bottom: 34 } };
function Providers({ children }: { children: ReactNode }) {
  return (
    <SafeAreaProvider initialMetrics={metrics}>
      <ToastProvider>{children}</ToastProvider>
    </SafeAreaProvider>
  );
}

beforeEach(() => {
  jest.clearAllMocks();
  useSignupDraft.getState().clear();
  availability.mockReturnValue("available");
  leak.mockResolvedValue("clean");
});

async function fillSignup(year = "2003") {
  await fireEvent.changeText(screen.getByLabelText("NICKNAME"), "Francesco");
  await fireEvent.changeText(screen.getByLabelText("EMAIL"), "Francesco@Example.com");
  await fireEvent.changeText(screen.getByLabelText("PASSWORD"), "Trento-Monaco-2026!");
  await fireEvent.changeText(screen.getByLabelText("GIORNO"), "14");
  await fireEvent.changeText(screen.getByLabelText("MESE"), "03");
  await fireEvent.changeText(screen.getByLabelText("ANNO"), year);
}

async function acceptAll() {
  const user = userEvent.setup();
  await user.press(screen.getByRole("checkbox", { name: /Informativa privacy/ }));
  await user.press(screen.getByRole("checkbox", { name: /regole della community/ }));
  return user;
}

describe("Registrazione", () => {
  test("invia a Supabase e passa al codice; la data di nascita resta solo in memoria", async () => {
    auth.signUp!.mockResolvedValue({ data: { user: { id: "u1" }, session: null }, error: null });
    await render(<SignupScreen />, { wrapper: Providers });
    await fillSignup();
    const continua = screen.getByRole("button", { name: "Continua" });
    expect(continua).toBeDisabled();

    const user = await acceptAll();
    expect(continua).toBeEnabled();
    await user.press(continua);

    expect(leak).toHaveBeenCalledWith("Trento-Monaco-2026!");
    expect(auth.signUp).toHaveBeenCalledWith({
      email: "francesco@example.com",
      password: "Trento-Monaco-2026!",
      options: { data: { nickname: "francesco" } },
    });
    expect(router.push).toHaveBeenCalledWith("/verify");
    expect(useSignupDraft.getState()).toMatchObject({
      nickname: "francesco",
      contactMode: "email",
      contact: "francesco@example.com",
      birth: { day: 14, month: 3, year: 2003 },
    });
  });

  test("sotto i 16 anni: messaggio, pulsante bloccato, nessun invio", async () => {
    await render(<SignupScreen />, { wrapper: Providers });
    await fillSignup("2015");
    await acceptAll();
    expect(screen.getByText(/riservata a chi ha almeno 16 anni. Non salviamo/)).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Continua" })).toBeDisabled();
    expect(auth.signUp).not.toHaveBeenCalled();
  });

  test("password trovata in una violazione: si ferma prima di Supabase", async () => {
    leak.mockResolvedValue("compromised");
    await render(<SignupScreen />, { wrapper: Providers });
    await fillSignup();
    const user = await acceptAll();
    await user.press(screen.getByRole("button", { name: "Continua" }));
    expect(screen.getByText(/comparsa in una violazione di dati/)).toBeOnTheScreen();
    expect(auth.signUp).not.toHaveBeenCalled();
  });

  test("nickname già preso: bloccato", async () => {
    availability.mockReturnValue("taken");
    await render(<SignupScreen />, { wrapper: Providers });
    await fillSignup();
    await acceptAll();
    expect(screen.getByText("Già preso. Prova una variante.")).toBeOnTheScreen();
    expect(screen.getByRole("button", { name: "Continua" })).toBeDisabled();
  });

  test("errore di Supabase tradotto in italiano", async () => {
    auth.signUp!.mockResolvedValue({ data: { user: null, session: null }, error: { code: "over_email_send_rate_limit" } });
    await render(<SignupScreen />, { wrapper: Providers });
    await fillSignup();
    const user = await acceptAll();
    await user.press(screen.getByRole("button", { name: "Continua" }));
    expect(screen.getByText("Hai chiesto troppi codici. Aspetta un minuto e riprova.")).toBeOnTheScreen();
    expect(router.push).not.toHaveBeenCalled();
  });
});

describe("Codice di conferma", () => {
  beforeEach(() => {
    useSignupDraft.getState().set({ contactMode: "email", contact: "francesco@example.com" });
  });

  test("con 6 cifre verifica subito il codice email", async () => {
    auth.verifyOtp!.mockResolvedValue({ data: {}, error: null });
    await render(<VerifyScreen />, { wrapper: Providers });
    expect(screen.getByText("francesco@example.com")).toBeOnTheScreen();
    await fireEvent.changeText(screen.getByLabelText("CODICE"), "12 34 56");
    expect(auth.verifyOtp).toHaveBeenCalledWith({ email: "francesco@example.com", token: "123456", type: "email" });
  });

  test("codice sbagliato: messaggio e campo svuotato", async () => {
    auth.verifyOtp!.mockResolvedValue({ data: {}, error: { code: "otp_expired" } });
    await render(<VerifyScreen />, { wrapper: Providers });
    await fireEvent.changeText(screen.getByLabelText("CODICE"), "000000");
    expect(screen.getByText(/scaduto o non è corretto/)).toBeOnTheScreen();
    expect(screen.getByLabelText("CODICE")).toHaveDisplayValue("");
  });

  test("reinvio possibile solo dopo 60 secondi", async () => {
    jest.useFakeTimers();
    try {
      auth.resend!.mockResolvedValue({ data: {}, error: null });
      await render(<VerifyScreen />, { wrapper: Providers });
      expect(screen.getByRole("button", { name: /Invia di nuovo tra 60s/ })).toBeDisabled();
      for (let i = 0; i < 60; i++) {
        await act(async () => {
          jest.advanceTimersByTime(1000);
        });
      }
      const user = userEvent.setup({ advanceTimers: jest.advanceTimersByTime });
      await user.press(screen.getByRole("button", { name: "Invia di nuovo il codice" }));
      expect(auth.resend).toHaveBeenCalledWith({ type: "signup", email: "francesco@example.com" });
      expect(screen.getByText("Codice inviato di nuovo.")).toBeOnTheScreen();
    } finally {
      jest.useRealTimers();
    }
  });

  test("senza bozza (app riaperta) propone di accedere", async () => {
    useSignupDraft.getState().clear();
    await render(<VerifyScreen />, { wrapper: Providers });
    expect(screen.getByText("Ricominciamo")).toBeOnTheScreen();
  });
});

describe("Accesso", () => {
  async function login(user: ReturnType<typeof userEvent.setup>) {
    await fireEvent.changeText(screen.getByLabelText("EMAIL"), "Francesco@Example.com");
    await fireEvent.changeText(screen.getByLabelText("PASSWORD"), "Trento-Monaco-2026!");
    await user.press(screen.getByRole("button", { name: "Accedi" }));
  }

  test("credenziali sbagliate: messaggio e password svuotata", async () => {
    auth.signInWithPassword!.mockResolvedValue({ data: {}, error: { code: "invalid_credentials" } });
    const user = userEvent.setup();
    await render(<LoginScreen />, { wrapper: Providers });
    await login(user);
    expect(auth.signInWithPassword).toHaveBeenCalledWith({
      email: "francesco@example.com",
      password: "Trento-Monaco-2026!",
    });
    expect(screen.getByText("Email o password non corrette.")).toBeOnTheScreen();
    expect(screen.getByLabelText("PASSWORD")).toHaveDisplayValue("");
  });

  test("account mai confermato: si riprende dal codice", async () => {
    auth.signInWithPassword!.mockResolvedValue({ data: {}, error: { code: "email_not_confirmed" } });
    const user = userEvent.setup();
    await render(<LoginScreen />, { wrapper: Providers });
    await login(user);
    expect(router.push).toHaveBeenCalledWith("/verify");
    expect(useSignupDraft.getState().contact).toBe("francesco@example.com");
  });
});
