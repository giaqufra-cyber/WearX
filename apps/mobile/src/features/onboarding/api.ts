/** Chiamate dell'onboarding: verifica dell'età e creazione del profilo. */
import { useQuery } from "@tanstack/react-query";
import type { AgeMethod, AgeSession, AgeStatus, OnboardingRequest, Profile } from "@wearx/api-types";
import * as Linking from "expo-linking";

import { useAuth } from "@/features/auth/AuthProvider";
import { apiGet, apiRequest } from "@/lib/api";

export const AGE_STATUS_KEY = ["age-status"] as const;

export function useAgeStatus(options: { poll?: boolean } = {}) {
  const { session } = useAuth();
  const token = session?.access_token;
  return useQuery({
    queryKey: [...AGE_STATUS_KEY, session?.user.id],
    queryFn: () => apiGet<AgeStatus>("/v1/age-verification", { token }),
    enabled: Boolean(token),
    // In attesa dell'esito si chiede ogni 2 secondi, finché la verifica è aperta.
    refetchInterval: (query) =>
      options.poll && (!query.state.data || query.state.data.latest?.status === "pending") ? 2000 : false,
    staleTime: 0,
  });
}

/** Dove il fornitore riporta l'utente: la schermata d'attesa dell'esito. */
export function ageReturnUrl(): string {
  return Linking.createURL("/age-wait");
}

export function startAgeSession(token: string, method: AgeMethod, declaredBirthDate: string): Promise<AgeSession> {
  return apiRequest<AgeSession>("POST", "/v1/age-verification/sessions", {
    token,
    body: { method, declared_birth_date: declaredBirthDate, return_url: ageReturnUrl() },
  });
}

export function createProfile(token: string, body: OnboardingRequest): Promise<Profile> {
  return apiRequest<Profile>("POST", "/v1/onboarding/profile", { token, body });
}

/** "2003-03-14" dalla data della bozza. */
export function isoDate(birth: { day: number; month: number; year: number }): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${birth.year}-${pad(birth.month)}-${pad(birth.day)}`;
}
