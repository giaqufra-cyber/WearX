/**
 * Quale server usa la demo sul telefono, e in che fase siamo. Solo con EXPO_PUBLIC_DEMO=1 e fuori
 * dal web (sul web la demo usa l'indirizzo della pagina, vedi lib/env).
 */
import AsyncStorage from "@react-native-async-storage/async-storage";
import { create } from "zustand";

import { normalizeServer, serverReachable } from "@/features/demo/server";
import { setDemoServer } from "@/lib/env";
import { recreateSupabase } from "@/lib/supabase";

export const DEMO_SERVER_KEY = "wearx.demo.server";

type Phase = "starting" | "checking" | "ready" | "setup";

type DemoState = {
  phase: Phase;
  /** Server in uso (fase "ready"). */
  server: string | null;
  /** Testo nel campo della schermata di collegamento. */
  draft: string;
  /** Perché serve un nuovo collegamento (server spento, link sbagliato…). */
  problem: string | null;
};

export const useDemoStore = create<DemoState>(() => ({
  phase: "starting",
  server: null,
  draft: "",
  problem: null,
}));

const UNREACHABLE =
  "Il server della demo non risponde. Il link cambia a ogni avvio: controlla che la demo sia accesa sul computer e usa il link nuovo.";
const INVALID = "Questo non sembra il link della demo (deve iniziare con https://).";

/** Prova a collegarsi; se riesce l'app riparte da capo verso quel server. */
export async function connectDemo(input: string): Promise<boolean> {
  const server = normalizeServer(input);
  if (!server) {
    useDemoStore.setState({ phase: "setup", draft: input, problem: INVALID });
    return false;
  }
  useDemoStore.setState({ phase: "checking", draft: server, problem: null });
  if (!(await serverReachable(server))) {
    useDemoStore.setState({ phase: "setup", draft: server, problem: UNREACHABLE });
    return false;
  }
  if (useDemoStore.getState().server !== server) {
    setDemoServer(server);
    recreateSupabase();
  }
  try {
    await AsyncStorage.setItem(DEMO_SERVER_KEY, server);
  } catch {
    // Non ricordarlo non è grave: al prossimo avvio si incolla di nuovo.
  }
  useDemoStore.setState({ phase: "ready", server, draft: server, problem: null });
  return true;
}

/** Primo avvio dell'app: prima il link del QR (se l'app è stata aperta così), poi l'ultimo usato. */
export async function startDemo(initialServer: string | null): Promise<void> {
  let saved: string | null = null;
  try {
    saved = await AsyncStorage.getItem(DEMO_SERVER_KEY);
  } catch {
    saved = null;
  }
  const candidate = initialServer ?? saved;
  if (!candidate) {
    useDemoStore.setState({ phase: "setup", draft: "", problem: null });
    return;
  }
  await connectDemo(candidate);
}

/** "Cambia server" (es. dalla schermata offline): si torna alla schermata di collegamento. */
export function changeDemoServer(): void {
  const { server, draft } = useDemoStore.getState();
  useDemoStore.setState({ phase: "setup", draft: server ?? draft, problem: null });
}
