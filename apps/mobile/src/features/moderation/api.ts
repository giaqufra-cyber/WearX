/** Segnalazioni, avvisi della moderazione e reclami. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Appeal, ModerationNotice, ReportReason, ReportReceipt, ReportRequest } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, apiGet, apiRequest } from "@/lib/api";

export const NOTICES_KEY = ["moderation-notices"] as const;

/** Motivi della segnalazione, nell'ordine in cui si mostrano. */
export const REASONS: ReadonlyArray<{ value: ReportReason; label: string; hint: string }> = [
  { value: "nudity", label: "Nudità o contenuti sessuali", hint: "Foto esplicite o allusive" },
  { value: "harassment", label: "Molestie o minacce", hint: "Insulti, minacce, dati personali di altri" },
  { value: "minor_safety", label: "Un minore è in pericolo", hint: "Abusi o sfruttamento di minori" },
  { value: "stolen_photo", label: "Foto rubata", hint: "La foto è tua o di qualcun altro" },
  { value: "wrong_style", label: "Stile sbagliato", hint: "Il fit non c'entra con lo stile" },
  { value: "dangerous_link", label: "Link pericoloso", hint: "Truffa, virus o sito per adulti" },
  { value: "spam", label: "Spam", hint: "Pubblicità ripetuta o contenuti fuori luogo" },
  { value: "other", label: "Altro", hint: "Un'altra violazione delle regole" },
];

export type ReportTarget = { type: "post"; id: string } | { type: "profile"; nickname: string };

export function useReport(target: ReportTarget) {
  const { session } = useAuth();
  return useMutation({
    mutationFn: ({ reason, details }: { reason: ReportReason; details: string }) => {
      const body: ReportRequest =
        target.type === "post"
          ? { target_type: "post", target_id: target.id, reason }
          : { target_type: "profile", nickname: target.nickname, reason };
      if (details.trim()) body.details = details.trim();
      return apiRequest<ReportReceipt>("POST", "/v1/reports", { token: session?.access_token, body });
    },
  });
}

export function reportError(error: unknown): string {
  const code = error instanceof ApiError ? error.code : "";
  if (code === "rate.limited") return "Hai inviato molte segnalazioni oggi: riprova domani.";
  if (code === "post.not_found" || code === "user.not_found") return "Questo contenuto non è più disponibile.";
  if (code === "report.own_content") return "Non puoi segnalare un tuo contenuto.";
  return "La segnalazione non è partita. Controlla la connessione e riprova.";
}

/** "entro 1 ora" / "entro 24 ore" */
export function reviewLabel(hours: number): string {
  return hours === 1 ? "entro 1 ora" : `entro ${hours} ore`;
}

export function useNotices() {
  const { session } = useAuth();
  return useQuery({
    queryKey: [...NOTICES_KEY, session?.user.id],
    queryFn: ({ signal }) => apiGet<ModerationNotice[]>("/v1/me/moderation", { token: session?.access_token, signal }),
    enabled: Boolean(session?.access_token),
  });
}

export function useAppeal() {
  const client = useQueryClient();
  const { session } = useAuth();
  return useMutation({
    mutationFn: ({ actionId, text }: { actionId: string; text: string }) =>
      apiRequest<Appeal>("POST", `/v1/me/moderation/${actionId}/appeal`, {
        token: session?.access_token,
        body: { text },
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: NOTICES_KEY }),
  });
}

export function appealError(error: unknown): string {
  const code = error instanceof ApiError ? error.code : "";
  if (code === "appeal.exists") return "Hai già fatto reclamo per questa decisione.";
  if (code === "appeal.expired") return "Il tempo per il reclamo (6 mesi) è scaduto.";
  return "Il reclamo non è partito. Controlla la connessione e riprova.";
}

export const ACTION_TITLES: Record<ModerationNotice["action"], string> = {
  hide: "Fit nascosto",
  remove: "Fit rimosso",
  restyle: "Stile cambiato",
  suspend: "Account sospeso",
  ban: "Account chiuso",
  restore: "Decisione annullata",
  warn: "Avviso",
  limit_posting: "Pubblicazione sospesa",
};

export const APPEAL_STATUS: Record<Appeal["status"], string> = {
  open: "Reclamo in esame",
  upheld: "Reclamo respinto",
  reversed: "Reclamo accolto",
};
