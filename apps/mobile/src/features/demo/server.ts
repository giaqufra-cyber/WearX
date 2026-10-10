/**
 * Server della demo (EXPO_PUBLIC_DEMO=1): regole pure, senza React né rete reale.
 *
 * La demo gira sul computer di chi la prova (`scripts/demo.sh`) dietro un link https che cambia a
 * ogni avvio. L'app lo riceve in due modi: incollato a mano o dal QR stampato dalla demo, che
 * apre `wearx://demo?server=<link>`.
 */

/** Indirizzi http ammessi solo sulla rete di casa (prove senza tunnel). */
const LOCAL_HTTP = /^http:\/\/(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)(:\d+)?$/;

/**
 * Indirizzo del server pulito (senza barra finale, percorso o parametri), oppure null se non è
 * utilizzabile. Accetta anche il link senza "https://" (es. copiato a metà).
 */
export function normalizeServer(input: string): string | null {
  let value = input.trim();
  if (!value) return null;
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(value)) value = `https://${value}`;
  const match = /^(https?):\/\/([^/?#\s]+)/i.exec(value);
  const [, scheme, host] = match ?? [];
  if (!scheme || !host) return null;
  const origin = `${scheme.toLowerCase()}://${host.toLowerCase()}`;
  if (origin.startsWith("https://")) {
    // Serve almeno un punto nel nome (es. qualcosa.trycloudflare.com) e niente credenziali.
    return /^https:\/\/[a-z0-9.-]+\.[a-z0-9-]+(:\d+)?$/.test(origin) ? origin : null;
  }
  return LOCAL_HTTP.test(origin) ? origin : null;
}

/** Server contenuto in un link `wearx://demo?server=…` (QR della demo), altrimenti null. */
export function serverFromLink(url: string | null | undefined): string | null {
  if (!url) return null;
  const query = /^wearx:\/\/\/?demo\/?\?(.*)$/i.exec(url.trim())?.[1];
  if (query === undefined) return null;
  for (const part of query.split("&")) {
    const [key, raw = ""] = part.split("=");
    if (key !== "server") continue;
    try {
      return normalizeServer(decodeURIComponent(raw));
    } catch {
      return null;
    }
  }
  return null;
}

/** Il server della demo risponde? (GET /healthz entro qualche secondo). */
export async function serverReachable(
  server: string,
  fetchImpl: typeof fetch = fetch,
  timeoutMs = 8000,
): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(`${server}/healthz`, { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}
