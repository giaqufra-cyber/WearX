/**
 * Disponibilità del nickname mentre si scrive: si chiede all'API solo dopo una pausa
 * di battitura e solo se il formato è già valido (niente richieste inutili).
 */
import { useQuery } from "@tanstack/react-query";
import type { NicknameCheck } from "@wearx/api-types";

import { apiRequest } from "@/lib/api";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { nicknameHint } from "@/lib/validation";

export const NICKNAME_DEBOUNCE_MS = 400;

export type NicknameAvailability = "idle" | "checking" | "available" | "taken" | "reserved" | "unknown";

export function useNicknameAvailability(nickname: string): NicknameAvailability {
  const normalized = nickname.trim().toLowerCase();
  const debounced = useDebouncedValue(normalized, NICKNAME_DEBOUNCE_MS);
  const formatOk = nicknameHint(debounced) === "ok";

  const query = useQuery({
    queryKey: ["nickname-check", debounced],
    queryFn: ({ signal }) =>
      apiRequest<NicknameCheck>("POST", "/v1/auth/nickname-check", { body: { nickname: debounced }, signal }),
    enabled: formatOk,
    staleTime: 30_000,
    retry: false,
  });

  if (nicknameHint(normalized) !== "ok") return "idle";
  if (normalized !== debounced || query.isPending) return "checking";
  if (query.isError) return "unknown";
  if (query.data.available) return "available";
  return query.data.reason === "reserved" ? "reserved" : "taken";
}
