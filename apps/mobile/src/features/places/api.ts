/**
 * Luogo del fit (seduta 35): ricerca dei luoghi (la fa il server, su OpenStreetMap) e
 * indirizzo per aprire il luogo in Mappe.
 */
import { useQuery } from "@tanstack/react-query";
import type { FitPlace, PlaceResults } from "@wearx/api-types";
import { Platform } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { apiGet } from "@/lib/api";
import { language } from "@/lib/i18n";

export const PLACE_QUERY_MIN = 2;
export const PLACE_QUERY_MAX = 80;
export const PLACE_DEBOUNCE_MS = 300;

/** Spazi multipli e a capo -> uno spazio; tagliata alla lunghezza massima. */
export function normalizePlaceQuery(raw: string): string {
  return raw.split(/\s+/).filter(Boolean).join(" ").slice(0, PLACE_QUERY_MAX);
}

/** Risultati per `query` (già normalizzata); sotto i 2 caratteri nessuna richiesta. */
export function usePlaceSearch(query: string) {
  const { session } = useAuth();
  const token = session?.access_token;
  return useQuery({
    queryKey: ["places", session?.user.id, language(), query],
    queryFn: ({ signal }) => apiGet<PlaceResults>(`/v1/places?q=${encodeURIComponent(query)}`, { token, signal }),
    enabled: Boolean(token) && query.length >= PLACE_QUERY_MIN,
    placeholderData: (previous) => previous,
    staleTime: 5 * 60_000,
  });
}

/** "Teatro alla Scala · Milano, Italia". */
export function placeLabel(place: Pick<FitPlace, "name" | "detail">): string {
  return place.detail ? `${place.name} · ${place.detail}` : place.name;
}

/**
 * Indirizzo per aprire il luogo: Apple Mappe su iPhone, Google Maps su Android e sul web.
 * Si passa il nome insieme alle coordinate, così Mappe mostra la scheda del posto.
 */
export function mapsUrl(place: FitPlace, os: string = Platform.OS): string {
  const name = encodeURIComponent(place.detail ? `${place.name}, ${place.detail}` : place.name);
  const ll = `${place.lat},${place.lon}`;
  if (os === "ios") return `https://maps.apple.com/?q=${encodeURIComponent(place.name)}&ll=${ll}`;
  if (os === "android") return `geo:${ll}?q=${ll}(${encodeURIComponent(place.name)})`;
  return `https://www.google.com/maps/search/?api=1&query=${name}`;
}
