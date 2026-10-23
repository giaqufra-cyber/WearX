/**
 * Stili proposti dalla community (seduta 30): elenco, proposta, "lo voglio".
 * Quando una richiesta porta la proposta alla soglia, lo stile nasce subito: si ricaricano gli
 * stili (catalogo, i tuoi) perché chi l'ha chiesto ci è già dentro.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { StyleProposal, StyleProposalCreated, StyleProposalList } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import type { StyleCategory } from "@/features/styles/catalog";
import { STYLES_KEY } from "@/features/styles/api";
import { ApiError, apiGet, apiRequest } from "@/lib/api";
import { t } from "@/lib/i18n";

export const PROPOSALS_KEY = ["style-proposals"] as const;

function useToken() {
  const { session } = useAuth();
  return { token: session?.access_token, uid: session?.user.id };
}

export function useProposals(query: string) {
  const { token, uid } = useToken();
  const q = query.trim();
  return useQuery({
    queryKey: [...PROPOSALS_KEY, uid, q],
    queryFn: ({ signal }) =>
      apiGet<StyleProposalList>(q ? `/v1/style-proposals?q=${encodeURIComponent(q)}` : "/v1/style-proposals", {
        token,
        signal,
      }),
    enabled: Boolean(token),
    placeholderData: (previous) => previous,
  });
}

export type ProposalDraft = { name: string; category: StyleCategory; tagline: string };

export function usePropose() {
  const client = useQueryClient();
  const { token } = useToken();
  return useMutation({
    mutationFn: (draft: ProposalDraft) =>
      apiRequest<StyleProposalCreated>("POST", "/v1/style-proposals", {
        token,
        body: { name: draft.name.trim(), category: draft.category, tagline: draft.tagline.trim() || null },
      }),
    onSuccess: (result) => afterChange(client, result.proposal),
  });
}

/** "Lo voglio" / ritira la richiesta. */
export function useSupport() {
  const client = useQueryClient();
  const { token } = useToken();
  return useMutation({
    mutationFn: ({ id, on }: { id: string; on: boolean }) =>
      apiRequest<StyleProposal>(on ? "PUT" : "DELETE", `/v1/style-proposals/${id}/support`, { token }),
    onSuccess: (proposal) => afterChange(client, proposal),
  });
}

function afterChange(client: ReturnType<typeof useQueryClient>, proposal: StyleProposal) {
  void client.invalidateQueries({ queryKey: PROPOSALS_KEY });
  if (proposal.status === "approved") void client.invalidateQueries({ queryKey: STYLES_KEY });
}

/** Lo stile che c'è già con quel nome (errore 409 `style.exists`). */
export function existingStyle(error: unknown): string | null {
  if (error instanceof ApiError && error.code === "style.exists" && typeof error.body?.slug === "string") {
    return error.body.slug;
  }
  return null;
}

export function proposalError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "style.exists") return t("Questo stile c'è già.");
    if (error.code === "proposal.limit") return t("Hai già 3 proposte aperte: aspetta che arrivino alla soglia.");
    if (error.code === "proposal.bad_name") return t("Scrivi un nome di almeno due lettere.");
    if (error.code === "proposal.not_found") return t("Questa proposta non c'è più.");
    if (error.code === "text.not_allowed") return t("Il nome contiene parole non ammesse.");
    if (error.code.startsWith("text.")) return error.title;
    if (error.status === 429) return t("Troppe proposte in poco tempo. Riprova domani.");
  }
  return t("Non è andata. Controlla la connessione e riprova.");
}

/** "12 su 25" e la quota (0-1) per la barra. */
export function progress(proposal: Pick<StyleProposal, "supports" | "threshold">): { label: string; ratio: number } {
  return {
    label: t("{supports} su {threshold}", { supports: proposal.supports, threshold: proposal.threshold }),
    ratio: Math.min(1, proposal.threshold > 0 ? proposal.supports / proposal.threshold : 0),
  };
}
