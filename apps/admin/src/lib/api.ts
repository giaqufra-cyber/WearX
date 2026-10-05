import { env } from "@/lib/env";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly title: string,
    readonly requestId?: string,
  ) {
    super(`${status} ${code}: ${title}`);
    this.name = "ApiError";
  }
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

/** Chiamata all'API con il token dello staff. Il token non viene mai salvato qui. */
export async function api<T>(method: Method, path: string, token: string, body?: unknown): Promise<T> {
  const response = await fetch(`${env.apiUrl}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      Authorization: `Bearer ${token}`,
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: "no-store",
  });
  if (!response.ok) {
    let code = `http.${response.status}`;
    let title = response.statusText;
    try {
      const data = (await response.json()) as { code?: unknown; title?: unknown };
      if (typeof data.code === "string") code = data.code;
      if (typeof data.title === "string") title = data.title;
    } catch {
      // corpo non leggibile
    }
    throw new ApiError(response.status, code, title, response.headers.get("x-request-id") ?? undefined);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "staff.mfa_required") return "Serve l'accesso con il secondo fattore.";
    if (error.code === "staff.admin_required") return "Serve il ruolo di amministratore.";
    return error.requestId ? `${error.title} (codice ${error.requestId})` : error.title;
  }
  return "Non riusciamo a raggiungere l'API. Controlla la connessione e riprova.";
}
