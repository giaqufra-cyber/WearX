/**
 * Client HTTP verso l'API WearX.
 * - aggiunge X-App-Version (l'API risponde 426 se l'app è troppo vecchia);
 * - trasforma le risposte application/problem+json in ApiError con `code` stabile.
 *
 * Dalla seduta 2 i tipi delle risposte arriveranno da packages/api-types (generati dall'OpenAPI).
 */
import Constants from "expo-constants";

export const API_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";
export const APP_VERSION = Constants.expoConfig?.version ?? "0.0.0";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly title: string,
    readonly requestId?: string,
    readonly body?: Record<string, unknown>,
  ) {
    super(`${status} ${code}: ${title}`);
    this.name = "ApiError";
  }
}

export async function parseError(response: Response): Promise<ApiError> {
  const requestId = response.headers.get("x-request-id") ?? undefined;
  const type = response.headers.get("content-type") ?? "";
  if (type.includes("application/problem+json") || type.includes("application/json")) {
    try {
      const body = (await response.json()) as Record<string, unknown>;
      const code = typeof body.code === "string" ? body.code : `http.${response.status}`;
      const title = typeof body.title === "string" ? body.title : response.statusText;
      return new ApiError(response.status, code, title, requestId, body);
    } catch {
      // corpo non leggibile: si ricade sul caso generico
    }
  }
  return new ApiError(response.status, `http.${response.status}`, response.statusText, requestId);
}

export async function apiGet<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    method: "GET",
    headers: {
      Accept: "application/json",
      "X-App-Version": APP_VERSION,
      ...init?.headers,
    },
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

/** Forma di GET /v1/config (provvisoria, sarà generata dall'OpenAPI). */
export type AppConfig = {
  min_app_version: string;
  feature_flags: Record<string, boolean>;
  styles: Array<{
    slug: string;
    name: string;
    tagline: string;
    tone: string;
    min_age_band: "16_17" | "18_plus";
    seasonal: boolean;
    active_until: string | null;
  }>;
  legal: { terms: string; privacy: string; community_rules: string; feed_explainer: string };
};
