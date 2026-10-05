/**
 * Eventi d'uso per gli Insight di chi pubblica (seduta 18). Solo i quattro della lista consentita
 * dell'API: fit visto, fit aperto, tocco sul link di un negozio, profilo visitato.
 *
 * - Si accumulano in memoria e partono a gruppi (ogni 30 secondi, a 20 eventi, o quando l'app va
 *   in background). Niente salvataggio sul telefono: se l'app si chiude, si perdono.
 * - Un fit visto o aperto (e un profilo visitato) conta una volta per sessione dell'app.
 * - Se la rete manca si riprova al giro dopo; se l'API rifiuta il gruppo, si scarta.
 */
import type { UsageEvent } from "@wearx/api-types";

import { ApiError, apiRequest } from "@/lib/api";

// Omit distribuito su ogni tipo di evento (un Omit sull'unione perderebbe i campi propri).
type NewEvent = UsageEvent extends infer E ? (E extends unknown ? Omit<E, "at"> : never) : never;

const MAX_QUEUE = 200;
const BATCH = 50;
const FLUSH_AT = 20;
export const FLUSH_EVERY_MS = 30_000;

let queue: UsageEvent[] = [];
let seen = new Set<string>();
let getToken: () => string | undefined = () => undefined;
let flushing: Promise<void> | null = null;

/** Chi manda gli eventi: il token della sessione corrente (o nessuno, da disconnessi). */
export function configureEvents(tokenGetter: () => string | undefined): void {
  getToken = tokenGetter;
}

/** Nuova sessione (accesso, uscita): si riparte da zero. */
export function resetEvents(): void {
  queue = [];
  seen = new Set();
}

function onceKey(event: NewEvent): string | null {
  if (event.name === "post_impression" || event.name === "post_open") return `${event.name}:${event.post_id}`;
  if (event.name === "profile_view") return `profile_view:${event.nickname.toLowerCase()}`;
  return null;
}

export function track(event: NewEvent): void {
  const key = onceKey(event);
  if (key) {
    if (seen.has(key)) return;
    seen.add(key);
  }
  queue.push({ ...event, at: new Date().toISOString() } as UsageEvent);
  if (queue.length > MAX_QUEUE) queue = queue.slice(-MAX_QUEUE);
  if (queue.length >= FLUSH_AT) void flushEvents();
}

export function pendingEvents(): readonly UsageEvent[] {
  return queue;
}

export function flushEvents(): Promise<void> {
  // Un invio alla volta. Il segnale si toglie in un passaggio successivo (finally), anche quando
  // non c'è nulla da mandare: altrimenti resterebbe "in corso" per sempre.
  flushing ??= send().finally(() => {
    flushing = null;
  });
  return flushing;
}

async function send(): Promise<void> {
  const token = getToken();
  while (token && queue.length > 0) {
    const batch = queue.slice(0, BATCH);
    try {
      await apiRequest("POST", "/v1/events", { token, body: { events: batch } });
    } catch (error) {
      // Rete assente o server occupato: si riprova dopo. Gruppo rifiutato: si scarta.
      const retry = !(error instanceof ApiError) || error.status === 429 || error.status >= 500;
      if (retry) return;
    }
    queue = queue.slice(batch.length);
  }
}
