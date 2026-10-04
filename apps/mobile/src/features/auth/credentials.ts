/** Credenziali nel formato che Supabase Auth si aspetta (email minuscola, telefono E.164). */
import type { SignInWithPasswordCredentials, SignUpWithPasswordCredentials } from "@supabase/supabase-js";

import { normalizePhone } from "@/features/auth/signupForm";

export type ContactMode = "email" | "phone";

export function normalizeContact(mode: ContactMode, raw: string): string {
  return mode === "email" ? raw.trim().toLowerCase() : normalizePhone(raw);
}

export function signUpCredentials(
  mode: ContactMode,
  contact: string,
  password: string,
  nickname: string,
  /** Dove riporta il link di conferma (solo email). */
  emailRedirectTo?: string,
): SignUpWithPasswordCredentials {
  // Il nickname va nei metadati solo come promemoria: il profilo vero si crea dopo la verifica dell'età.
  const options = { data: { nickname: nickname.trim().toLowerCase() } };
  const value = normalizeContact(mode, contact);
  return mode === "email"
    ? { email: value, password, options: emailRedirectTo ? { ...options, emailRedirectTo } : options }
    : { phone: value, password, options: { ...options, channel: "sms" } };
}

export function signInCredentials(mode: ContactMode, contact: string, password: string): SignInWithPasswordCredentials {
  const value = normalizeContact(mode, contact);
  return mode === "email" ? { email: value, password } : { phone: value, password };
}
