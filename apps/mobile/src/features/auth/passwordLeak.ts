/**
 * Controllo "password già finita in una violazione di dati" con il servizio Have I Been Pwned,
 * in modalità k-anonymity: si invia solo l'inizio (5 caratteri) dell'hash SHA-1 della password,
 * mai la password né l'hash completo. Il confronto avviene sul telefono.
 * Se il servizio non risponde non si blocca la registrazione (il controllo è un aiuto in più).
 */
import { CryptoDigestAlgorithm, digestStringAsync } from "expo-crypto";

const RANGE_URL = "https://api.pwnedpasswords.com/range/";

export type LeakCheck = "compromised" | "clean" | "unknown";

export async function checkPasswordLeak(
  password: string,
  fetchImpl: typeof fetch = fetch,
  sha1: (value: string) => Promise<string> = (value) =>
    digestStringAsync(CryptoDigestAlgorithm.SHA1, value),
): Promise<LeakCheck> {
  try {
    const hash = (await sha1(password)).toUpperCase();
    const prefix = hash.slice(0, 5);
    const suffix = hash.slice(5);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 4000);
    const response = await fetchImpl(RANGE_URL + prefix, {
      // Le risposte vengono riempite con voci finte: chi osserva il traffico non capisce l'esito.
      headers: { "Add-Padding": "true" },
      signal: controller.signal,
    }).finally(() => clearTimeout(timeout));
    if (!response.ok) return "unknown";
    const body = await response.text();
    for (const line of body.split("\n")) {
      const [candidate, count] = line.trim().split(":");
      if (candidate === suffix && Number(count) > 0) return "compromised";
    }
    return "clean";
  } catch {
    return "unknown";
  }
}
