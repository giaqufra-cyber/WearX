/**
 * Dove deve stare l'utente, dato lo stato di sessione e profilo.
 * Funzione pura: è il cuore della navigazione protetta ed è testata a parte.
 */
import { ApiError } from "@/lib/api";

export type AppRoute = "loading" | "auth" | "onboarding" | "app" | "suspended" | "deleting" | "offline";

export type RouteInput = {
  /** La sessione salvata è ancora in lettura. */
  initializing: boolean;
  hasSession: boolean;
  /** Recupero della password in corso: la sessione c'è già, ma prima va scelta la nuova password. */
  recovering?: boolean;
  me:
    | { state: "loading" }
    | { state: "ok"; status: "active" | "suspended" | "pending_deletion" }
    | { state: "error"; error: unknown };
};

export function decideRoute({ initializing, hasSession, recovering = false, me }: RouteInput): AppRoute {
  if (initializing) return "loading";
  if (!hasSession || recovering) return "auth";
  if (me.state === "loading") return "loading";
  if (me.state === "error") {
    if (me.error instanceof ApiError) {
      if (me.error.code === "onboarding.required") return "onboarding";
      // Token non più valido (scaduto e non rinnovabile, revocato): si torna all'accesso.
      if (me.error.status === 401) return "auth";
    }
    // Server irraggiungibile o errore imprevisto: schermata con "Riprova", senza disconnettere.
    return "offline";
  }
  if (me.status === "suspended") return "suspended";
  if (me.status === "pending_deletion") return "deleting";
  return "app";
}
