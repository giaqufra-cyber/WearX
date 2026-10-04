/**
 * Stato di accesso dell'app: sessione Supabase + profilo WearX (GET /v1/me).
 * Da qui il layout principale decide quali gruppi di schermate sono raggiungibili.
 */
import type { Session } from "@supabase/supabase-js";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Profile } from "@wearx/api-types";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { decideRoute, type AppRoute } from "@/features/auth/routing";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { apiGet } from "@/lib/api";
import { supabase } from "@/lib/supabase";

type AuthState = {
  route: AppRoute;
  session: Session | null;
  profile: Profile | null;
  retry: () => void;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export const ME_QUERY_KEY = ["me"] as const;

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [session, setSession] = useState<Session | null>(null);
  const [initializing, setInitializing] = useState(true);

  useEffect(() => {
    let active = true;
    supabase.auth
      .getSession()
      .then(({ data }) => {
        if (active) setSession(data.session);
      })
      .finally(() => {
        if (active) setInitializing(false);
      });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);

  const token = session?.access_token;
  const me = useQuery({
    queryKey: [...ME_QUERY_KEY, session?.user.id],
    queryFn: () => apiGet<Profile>("/v1/me", { token }),
    enabled: Boolean(token),
    // Gli errori "previsti" (profilo da creare, token non valido) non si ritentano.
    retry: (count, error) =>
      count < 2 && !(error instanceof Error && "status" in error && [401, 403, 409].includes(Number(error.status))),
    staleTime: 60_000,
  });

  const route = decideRoute({
    initializing,
    hasSession: Boolean(session),
    me: me.isPending
      ? { state: "loading" }
      : me.isError
        ? { state: "error", error: me.error }
        : { state: "ok", status: me.data.status },
  });

  const retry = useCallback(() => {
    void me.refetch();
  }, [me]);

  const signOut = useCallback(async () => {
    await supabase.auth.signOut();
    useSignupDraft.getState().clear();
    queryClient.removeQueries({ queryKey: ME_QUERY_KEY });
  }, [queryClient]);

  const value = useMemo<AuthState>(
    () => ({ route, session, profile: me.data ?? null, retry, signOut }),
    [route, session, me.data, retry, signOut],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth va usato dentro <AuthProvider>");
  return value;
}
