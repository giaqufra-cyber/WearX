/** Segnalazioni, avvisi della moderazione e reclami. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Appeal, ModerationNotice, ReportReason, ReportReceipt, ReportRequest } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { N_, t } from "@/lib/i18n";

export const NOTICES_KEY = ["moderation-notices"] as const;

/** Motivi della segnalazione, nell'ordine in cui si mostrano. */
export const REASONS: ReadonlyArray<{ value: ReportReason; label: string; hint: string }> = [
  { value: "nudity", label: N_("Nudità o contenuti sessuali"), hint: N_("Foto esplicite o allusive") },
  { value: "harassment", label: N_("Molestie o minacce"), hint: N_("Insulti, minacce, dati personali di altri") },
  { value: "minor_safety", label: N_("Un minore è in pericolo"), hint: N_("Abusi o sfruttamento di minori") },
  { value: "stolen_photo", label: N_("Foto rubata"), hint: N_("La foto è tua o di qualcun altro") },
  { value: "wrong_style", label: N_("Stile sbagliato"), hint: N_("Il fit non c'entra con lo stile") },
  { value: "dangerous_link", label: N_("Link pericoloso"), hint: N_("Truffa, virus o sito per adulti") },
  { value: "spam", label: N_("Spam"), hint: N_("Pubblicità ripetuta o contenuti fuori luogo") },
  { value: "other", label: N_("Altro"), hint: N_("Un'altra violazione delle regole") },
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
  if (code === "rate.limited") return t("Hai inviato molte segnalazioni oggi: riprova domani.");
  if (code === "post.not_found" || code === "user.not_found") return t("Questo contenuto non è più disponibile.");
  if (code === "report.own_content") return t("Non puoi segnalare un tuo contenuto.");
  return t("La segnalazione non è partita. Controlla la connessione e riprova.");
}

/** "entro 1 ora" / "entro 24 ore" */
export function reviewLabel(hours: number): string {
  return hours === 1 ? t("entro 1 ora") : t("entro {hours} ore", { hours });
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
  if (code === "appeal.exists") return t("Hai già fatto reclamo per questa decisione.");
  if (code === "appeal.expired") return t("Il tempo per il reclamo (6 mesi) è scaduto.");
  return t("Il reclamo non è partito. Controlla la connessione e riprova.");
}

export const ACTION_TITLES: Record<ModerationNotice["action"], string> = {
  hide: N_("Fit nascosto"),
  remove: N_("Fit rimosso"),
  restyle: N_("Stile cambiato"),
  suspend: N_("Account sospeso"),
  ban: N_("Account chiuso"),
  restore: N_("Decisione annullata"),
  warn: N_("Avviso"),
  limit_posting: N_("Pubblicazione sospesa"),
};

/** Titolo dell'avviso: "rimosso" sul profilo vuol dire bio e foto tolte (seduta 27). */
export function noticeTitle(notice: Pick<ModerationNotice, "action" | "target_type">): string {
  if (notice.action === "remove" && notice.target_type === "profile") return t("Bio e foto profilo tolte");
  return t(ACTION_TITLES[notice.action]);
}

export const APPEAL_STATUS: Record<Appeal["status"], string> = {
  open: N_("Reclamo in esame"),
  upheld: N_("Reclamo respinto"),
  reversed: N_("Reclamo accolto"),
};
