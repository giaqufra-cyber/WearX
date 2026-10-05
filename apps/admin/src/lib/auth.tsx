"use client";

/**
 * Accesso dello staff: email e password Supabase, poi SEMPRE il secondo fattore (TOTP).
 * L'API accetta solo token con aal2. La sessione resta in sessionStorage: chiusa la scheda,
 * si rientra da capo. In sviluppo si può incollare un token (server Supabase finto in locale).
 */
import type { StaffMe } from "@wearx/api-types";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "@/lib/api";
import { env } from "@/lib/env";

export type AuthStatus =
  | "loading"
  | "signed_out"
  | "enroll_mfa" // nessun fattore: va configurata l'app di autenticazione
  | "verify_mfa" // fattore presente: serve il codice
  | "not_staff"
  | "ready";

type Enrollment = { factorId: string; qr: string; secret: string };

type AuthValue = {
  status: AuthStatus;
  token: string | null;
  me: StaffMe | null;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  startEnrollment: () => Promise<Enrollment>;
  verify: (code: string, factorId?: string) => Promise<void>;
  signInWithToken: (token: string) => Promise<void>;
  signOut: () => Promise<void>;
};

const DEV_TOKEN_KEY = "wearx-admin-dev-token";
const AuthContext = createContext<AuthValue | null>(null);

let client: SupabaseClient | null = null;
function supabase(): SupabaseClient {
  client ??= createClient(env.supabaseUrl, env.supabaseKey, {
    auth: {
      storage: typeof window === "undefined" ? undefined : window.sessionStorage,
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
    },
  });
  return client;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [token, setToken] = useState<string | null>(null);
  const [me, setMe] = useState<StaffMe | null>(null);
  const [error, setError] = useState<string | null>(null);

  /** Con un token aal2 si chiede all'API chi siamo: se non siamo staff, niente pannello. */
  const checkStaff = useCallback(async (accessToken: string) => {
    try {
      const who = await api<StaffMe>("GET", "/v1/admin/me", accessToken);
      setToken(accessToken);
      setMe(who);
      setStatus("ready");
    } catch (caught) {
      setToken(null);
      setMe(null);
      if (caught instanceof ApiError && caught.code === "staff.mfa_required") setStatus("verify_mfa");
      else if (caught instanceof ApiError && caught.status === 404) setStatus("not_staff");
      else {
        setError("Non riusciamo a raggiungere l'API.");
        setStatus("signed_out");
      }
    }
  }, []);

  const evaluate = useCallback(async () => {
    if (env.devLogin) {
      const devToken = window.sessionStorage.getItem(DEV_TOKEN_KEY);
      if (devToken) return checkStaff(devToken);
    }
    const { data } = await supabase().auth.getSession();
    const session = data.session;
    if (!session) {
      setStatus("signed_out");
      return;
    }
    const aal = await supabase().auth.mfa.getAuthenticatorAssuranceLevel();
    if (aal.data?.currentLevel === "aal2") return checkStaff(session.access_token);
    const factors = await supabase().auth.mfa.listFactors();
    const verified = factors.data?.totp.filter((f) => f.status === "verified") ?? [];
    setStatus(verified.length > 0 ? "verify_mfa" : "enroll_mfa");
  }, [checkStaff]);

  useEffect(() => {
    void evaluate();
    if (env.devLogin && window.sessionStorage.getItem(DEV_TOKEN_KEY)) return;
    const { data } = supabase().auth.onAuthStateChange((event) => {
      if (event === "TOKEN_REFRESHED" || event === "SIGNED_OUT") void evaluate();
    });
    return () => data.subscription.unsubscribe();
  }, [evaluate]);

  const value = useMemo<AuthValue>(
    () => ({
      status,
      token,
      me,
      error,
      signIn: async (email, password) => {
        setError(null);
        const { error: failed } = await supabase().auth.signInWithPassword({ email, password });
        if (failed) {
          setError("Email o password non corretti.");
          return;
        }
        await evaluate();
      },
      startEnrollment: async () => {
        const { data, error: failed } = await supabase().auth.mfa.enroll({
          factorType: "totp",
          friendlyName: `WearX staff ${new Date().toISOString().slice(0, 10)}`,
        });
        if (failed || !data) throw new Error("Configurazione del secondo fattore non riuscita.");
        return { factorId: data.id, qr: data.totp.qr_code, secret: data.totp.secret };
      },
      verify: async (code, factorId) => {
        setError(null);
        let id = factorId;
        if (!id) {
          const factors = await supabase().auth.mfa.listFactors();
          id = factors.data?.totp.find((f) => f.status === "verified")?.id;
        }
        if (!id) {
          setStatus("enroll_mfa");
          return;
        }
        const { error: failed } = await supabase().auth.mfa.challengeAndVerify({ factorId: id, code });
        if (failed) {
          setError("Codice non valido o scaduto.");
          return;
        }
        await evaluate();
      },
      signInWithToken: async (devToken) => {
        if (!env.devLogin) return;
        window.sessionStorage.setItem(DEV_TOKEN_KEY, devToken.trim());
        await checkStaff(devToken.trim());
      },
      signOut: async () => {
        window.sessionStorage.removeItem(DEV_TOKEN_KEY);
        await supabase().auth.signOut();
        setToken(null);
        setMe(null);
        setStatus("signed_out");
      },
    }),
    [status, token, me, error, evaluate, checkStaff],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth fuori da AuthProvider");
  return value;
}
