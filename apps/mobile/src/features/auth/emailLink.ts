/**
 * Conferma dell'email tramite link (modello predefinito di Supabase).
 * Il link passa da Supabase, che conferma l'indirizzo, e riapre l'app su /verify con
 * `?code=…` (PKCE) oppure con `?error_code=…` se il link è scaduto o già usato.
 */
import * as Linking from "expo-linking";

/** Indirizzo a cui Supabase rimanda dopo il clic: wearx://verify (o exp://…/--/verify in sviluppo). */
export function emailRedirectUrl(): string {
  return Linking.createURL("/verify");
}

export type AuthRedirect =
  | { kind: "code"; code: string }
  | { kind: "error"; code: string; description?: string }
  | null;

type Params = Record<string, string | string[] | undefined>;

const first = (value: string | string[] | undefined) => (Array.isArray(value) ? value[0] : value);

export function parseAuthRedirect(params: Params): AuthRedirect {
  const errorCode = first(params.error_code) ?? first(params.error);
  if (errorCode) return { kind: "error", code: errorCode, description: first(params.error_description) };
  const code = first(params.code);
  // Codice PKCE: un UUID. Qualunque altra cosa si ignora.
  if (code && /^[A-Za-z0-9-]{20,100}$/.test(code)) return { kind: "code", code };
  return null;
}
