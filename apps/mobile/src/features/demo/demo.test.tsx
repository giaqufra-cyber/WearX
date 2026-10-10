import AsyncStorage from "@react-native-async-storage/async-storage";
import { fireEvent, render, screen } from "@testing-library/react-native";

import { DemoSetup } from "@/features/demo/DemoGate";
import { DEMO_SERVER_KEY, connectDemo, changeDemoServer, startDemo, useDemoStore } from "@/features/demo/demoStore";
import { normalizeServer, serverFromLink, serverReachable } from "@/features/demo/server";
import { env } from "@/lib/env";

jest.mock("@react-native-async-storage/async-storage", () =>
  require("@react-native-async-storage/async-storage/jest/async-storage-mock"),
);
jest.mock("@/lib/supabase", () => ({ recreateSupabase: jest.fn() }));
jest.mock("expo-splash-screen", () => ({ hideAsync: jest.fn(async () => undefined) }));

const LINK = "https://quiet-river-blue-moon.trycloudflare.com";

function okFetch(ok: boolean) {
  return jest.fn(async () => ({ ok }) as Response);
}

beforeEach(async () => {
  useDemoStore.setState({ phase: "starting", server: null, draft: "", problem: null });
  await AsyncStorage.clear();
});

describe("indirizzo della demo", () => {
  it("accetta il link della demo anche senza https:// o con percorso e barra finale", () => {
    expect(normalizeServer(LINK)).toBe(LINK);
    expect(normalizeServer(`  ${LINK}/  `)).toBe(LINK);
    expect(normalizeServer("Quiet-River-Blue-Moon.trycloudflare.com/feed?x=1")).toBe(LINK);
  });

  it("rifiuta testo che non è un server e http fuori dalla rete di casa", () => {
    expect(normalizeServer("")).toBeNull();
    expect(normalizeServer("ciao")).toBeNull();
    expect(normalizeServer("http://example.com")).toBeNull();
    expect(normalizeServer("ftp://example.com")).toBeNull();
    expect(normalizeServer("https://user:pw@example.com")).toBeNull();
    expect(normalizeServer("http://192.168.1.20:8090")).toBe("http://192.168.1.20:8090");
  });

  it("legge il server dal link del QR", () => {
    expect(serverFromLink(`wearx://demo?server=${encodeURIComponent(LINK)}`)).toBe(LINK);
    expect(serverFromLink(`wearx://demo?server=${LINK}`)).toBe(LINK);
    expect(serverFromLink(`wearx:///demo/?a=1&server=${LINK}`)).toBe(LINK);
    expect(serverFromLink("wearx://verify?code=abc")).toBeNull();
    expect(serverFromLink("wearx://demo?server=%E0%A4%A")).toBeNull();
    expect(serverFromLink(null)).toBeNull();
  });

  it("controlla che il server risponda", async () => {
    await expect(serverReachable(LINK, okFetch(true) as unknown as typeof fetch)).resolves.toBe(true);
    await expect(serverReachable(LINK, okFetch(false) as unknown as typeof fetch)).resolves.toBe(false);
    const broken = jest.fn(async () => {
      throw new TypeError("Network request failed");
    });
    await expect(serverReachable(LINK, broken as unknown as typeof fetch)).resolves.toBe(false);
  });
});

describe("collegamento al server", () => {
  const realFetch = global.fetch;
  const { apiUrl, supabaseUrl } = env;
  afterEach(() => {
    global.fetch = realFetch;
    env.apiUrl = apiUrl;
    env.supabaseUrl = supabaseUrl;
  });

  it("se il server risponde lo usa per API e accesso e lo ricorda", async () => {
    global.fetch = okFetch(true) as unknown as typeof fetch;
    await expect(connectDemo(LINK)).resolves.toBe(true);
    expect(useDemoStore.getState()).toMatchObject({ phase: "ready", server: LINK });
    expect(env.apiUrl).toBe(LINK);
    expect(env.supabaseUrl).toBe(LINK);
    expect(await AsyncStorage.getItem(DEMO_SERVER_KEY)).toBe(LINK);
  });

  it("se il server è spento resta sulla schermata di collegamento con il motivo", async () => {
    global.fetch = okFetch(false) as unknown as typeof fetch;
    await expect(connectDemo(LINK)).resolves.toBe(false);
    expect(useDemoStore.getState()).toMatchObject({ phase: "setup", server: null, draft: LINK });
    expect(useDemoStore.getState().problem).toMatch(/non risponde/);
  });

  it("all'avvio preferisce il link del QR all'ultimo server usato", async () => {
    global.fetch = okFetch(true) as unknown as typeof fetch;
    await AsyncStorage.setItem(DEMO_SERVER_KEY, "https://old-link.trycloudflare.com");
    await startDemo(LINK);
    expect(useDemoStore.getState().server).toBe(LINK);
  });

  it("senza link né server salvato chiede il collegamento", async () => {
    await startDemo(null);
    expect(useDemoStore.getState()).toMatchObject({ phase: "setup", draft: "" });
  });

  it("'Cambia server' riporta alla schermata con il link attuale", async () => {
    global.fetch = okFetch(true) as unknown as typeof fetch;
    await connectDemo(LINK);
    changeDemoServer();
    expect(useDemoStore.getState()).toMatchObject({ phase: "setup", draft: LINK });
  });

  it("la schermata collega il link incollato", async () => {
    global.fetch = okFetch(true) as unknown as typeof fetch;
    useDemoStore.setState({ phase: "setup" });
    await render(<DemoSetup />);
    await fireEvent.changeText(screen.getByLabelText("Link della demo"), "quiet-river-blue-moon.trycloudflare.com");
    await fireEvent.press(screen.getByRole("button", { name: "Collega" }));
    expect(useDemoStore.getState()).toMatchObject({ phase: "ready", server: LINK });
  });

  it("la schermata spiega un link sbagliato", async () => {
    useDemoStore.setState({ phase: "setup" });
    await render(<DemoSetup />);
    await fireEvent.changeText(screen.getByLabelText("Link della demo"), "non è un link");
    await fireEvent.press(screen.getByRole("button", { name: "Collega" }));
    expect(await screen.findByText(/non sembra il link della demo/)).toBeTruthy();
  });
});
