/** Insight: come vanno i tuoi fit. Dati del riepilogo notturno, con le soglie dell'API. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { InsightMetric, InsightPeriod, Insights } from "@wearx/api-types";

import { useAuth } from "@/features/auth/AuthProvider";
import { apiGet } from "@/lib/api";

export const INSIGHTS_KEY = ["insights"] as const;

export function useInsights(days: InsightPeriod) {
  const { session } = useAuth();
  const token = session?.access_token;
  return useQuery({
    queryKey: [...INSIGHTS_KEY, session?.user.id, days],
    queryFn: ({ signal }) => apiGet<Insights>(`/v1/me/insights?days=${days}`, { token, signal }),
    enabled: Boolean(token),
    placeholderData: keepPreviousData,
    staleTime: 10 * 60_000,
  });
}

/** 12345 -> "12.345" (separatore italiano, senza dipendere da Intl). */
export function formatInt(value: number): string {
  return String(Math.round(value)).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/** Valore di una metrica: null = "meno di 5" (soglia di riservatezza). */
export function formatMetric(value: number | null | undefined): string {
  return value === null || value === undefined ? "<5" : formatInt(value);
}

/** Variazione rispetto al periodo prima: "+12%", "−8%", "="; null se non confrontabile. */
export function formatChange(metric: InsightMetric): string | null {
  if (metric.change === null) return null;
  const rounded = Math.round(metric.change);
  if (rounded === 0) return "=";
  return rounded > 0 ? `+${formatInt(rounded)}%` : `−${formatInt(-rounded)}%`;
}

export function shortDate(iso: string): string {
  // Le date dell'API sono giorni ("2026-10-04"): mezzogiorno evita salti di fuso.
  return new Date(`${iso}T12:00:00`).toLocaleDateString("it-IT", { day: "numeric", month: "short" });
}

export function weekdayDate(iso: string): string {
  return new Date(`${iso}T12:00:00`).toLocaleDateString("it-IT", { weekday: "short", day: "numeric", month: "short" });
}
