/**
 * Client HTTP verso l'API WearX.
 * - aggiunge X-App-Version (l'API risponde 426 se l'app è troppo vecchia);
 * - trasforma le risposte application/problem+json in ApiError con `code` stabile.
 *
 * I tipi delle risposte arrivano da @wearx/api-types, generati dall'OpenAPI dell'API.
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

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type RequestOptions = {
  body?: unknown;
  /** Token di accesso Supabase. Mai salvato qui: lo passa chi chiama, preso dalla sessione. */
  token?: string;
  /** Per azioni ripetibili in caso di rete instabile (voti, pubblicazioni): stessa chiave = una sola esecuzione. */
  idempotencyKey?: string;
  signal?: AbortSignal;
};

export async function apiRequest<T>(method: Method, path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    "X-App-Version": APP_VERSION,
  };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.token) headers.Authorization = `Bearer ${options.token}`;
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
    signal: options.signal,
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function apiGet<T>(path: string, options?: Omit<RequestOptions, "body">): Promise<T> {
  return apiRequest<T>("GET", path, options);
}

export type { AppConfig } from "@wearx/api-types";
