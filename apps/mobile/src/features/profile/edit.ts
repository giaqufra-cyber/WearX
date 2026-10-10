/**
 * Modifica profilo (seduta 27): bio e foto profilo.
 * Le regole della bio sono quelle del server (`text_policy.clean_bio`), per avvisare subito.
 */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Profile, ProfileUpdate } from "@wearx/api-types";

import { ME_QUERY_KEY, useAuth } from "@/features/auth/AuthProvider";
import { PORTFOLIO_KEY } from "@/features/portfolio/api";
import { ApiError, apiRequest } from "@/lib/api";

export const BIO_MAX_CHARS = 150;
export const BIO_MAX_LINES = 4;

/** Caratteri come li conta il server (un'emoji vale 1, non 2). */
export function bioLength(text: string): number {
  return [...text.normalize("NFC").trim()].length;
}

export function bioProblem(text: string): string | null {
  const clean = text.normalize("NFC").trim();
  if (!clean) return null;
  if (bioLength(clean) > BIO_MAX_CHARS) return `Massimo ${BIO_MAX_CHARS} caratteri.`;
  if (clean.split("\n").length > BIO_MAX_LINES) return `Massimo ${BIO_MAX_LINES} righe.`;
  return null;
}

export function saveError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "avatar.not_allowed") return "Questa foto non può essere usata come foto profilo.";
    if (error.code === "avatar.unavailable") return "La foto non è pronta. Riprova a sceglierla.";
    if (error.code === "text.not_allowed") return "La bio contiene parole non ammesse.";
    if (error.code.startsWith("text.")) return error.title;
    if (error.status === 429) return "Troppe modifiche in poco tempo. Riprova più tardi.";
  }
  return "Modifiche non salvate. Controlla la connessione e riprova.";
}

/** Salva bio e/o foto; aggiorna il profilo in memoria e la pagina del profilo. */
export function useSaveProfile() {
  const client = useQueryClient();
  const { session } = useAuth();
  const uid = session?.user.id;
  return useMutation({
    mutationFn: (patch: ProfileUpdate) =>
      apiRequest<Profile>("PATCH", "/v1/me", { token: session?.access_token, body: patch }),
    onSuccess: (saved) => {
      client.setQueryData([...ME_QUERY_KEY, uid], saved);
      void client.invalidateQueries({ queryKey: PORTFOLIO_KEY });
    },
  });
}
