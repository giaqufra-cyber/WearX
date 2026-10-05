import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import AppealsPage from "@/app/appeals/page";
import StaffPage from "@/app/staff/page";
import StylesPage from "@/app/styles/page";

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ token: "tok", me: { role: "admin", nickname: "boss" } }) }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a> }));

type Call = { url: string; method: string; body: unknown };
let calls: Call[];

function serve(routes: Record<string, unknown>) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : undefined });
      const key = Object.keys(routes).find((k) => `${method} ${url}`.includes(k));
      const body = key ? routes[key] : { code: "x", title: "inatteso" };
      return new Response(body === null ? null : JSON.stringify(body), {
        status: body === null ? 204 : key ? 200 : 500,
        headers: { "content-type": "application/json" },
      });
    }),
  );
}

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>;
}

const writes = () => calls.filter((c) => c.method !== "GET");

beforeEach(() => (calls = []));
afterEach(() => vi.unstubAllGlobals());

describe("Le scritture mandano solo i campi che l'API accetta", () => {
  test("reclamo: decisione e risposta, l'id nel percorso", async () => {
    serve({
      "GET http://localhost:8000/v1/admin/appeals": [
        {
          id: "ap1",
          nickname: "fra.fit",
          text: "È un costume da bagno.",
          created_at: "2026-10-05T08:00:00Z",
          action: {
            id: "a1",
            action: "hide",
            ground: "nudity",
            automated: false,
            created_at: "2026-10-05T07:00:00Z",
            expires_at: null,
            statement: "Il tuo fit è stato nascosto.",
            appeal_status: "open",
          },
        },
      ],
      "POST http://localhost:8000/v1/admin/appeals/ap1": { id: "ap1" },
    });
    render(<AppealsPage />, { wrapper });
    expect(await screen.findByText("È un costume da bagno.")).toBeTruthy();
    const accept = screen.getByRole("button", { name: "Accogli e annulla la decisione" }) as HTMLButtonElement;
    expect(accept.disabled).toBe(true); // serve la risposta per la persona
    await userEvent.type(screen.getByLabelText(/Risposta per la persona/), "Costume ammesso.");
    await userEvent.click(accept);
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(writes()[0]).toEqual({
      url: "http://localhost:8000/v1/admin/appeals/ap1",
      method: "POST",
      body: { decision: "reverse", note: "Costume ammesso." },
    });
  });

  test("stile: modifica senza slug nel corpo; nuovo stile con lo slug dal nome", async () => {
    const style = {
      slug: "gala",
      name: "Galà",
      tagline: "Serate eleganti",
      tone: "#3A1418",
      min_age_band: "16_17",
      active_from: null,
      active_until: null,
      sort_order: 10,
      is_active: true,
      members: 40,
      posts_7d: 3,
    };
    serve({
      "GET http://localhost:8000/v1/admin/styles": [style],
      "PATCH http://localhost:8000/v1/admin/styles/gala": style,
      "POST http://localhost:8000/v1/admin/styles": { ...style, slug: "apres-ski" },
    });
    render(<StylesPage />, { wrapper });
    await userEvent.click(await screen.findByRole("button", { name: "Modifica" }));
    await userEvent.selectOptions(screen.getByLabelText("Età minima"), "18_plus");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(writes()[0]!.method).toBe("PATCH");
    expect(writes()[0]!.body).not.toHaveProperty("slug");
    expect(writes()[0]!.body).toMatchObject({ min_age_band: "18_plus", tone: "#3A1418", active_from: null });

    await userEvent.click(screen.getByRole("button", { name: "Nuovo stile" }));
    await userEvent.type(screen.getByLabelText("Nome", { exact: true }), "Après Ski");
    expect((screen.getByLabelText(/Slug/) as HTMLInputElement).value).toBe("apres-ski");
    await userEvent.type(screen.getByLabelText("Descrizione breve"), "Montagna e lana");
    await userEvent.click(screen.getByRole("button", { name: "Salva" }));
    await waitFor(() => expect(writes()).toHaveLength(2));
    expect(writes()[1]!.body).toMatchObject({ slug: "apres-ski", name: "Après Ski", min_age_band: "16_17" });
  });

  test("staff: solo il ruolo nel corpo", async () => {
    serve({
      "GET http://localhost:8000/v1/admin/staff": [],
      "PUT http://localhost:8000/v1/admin/staff/nuova.mod": { nickname: "nuova.mod", role: "moderator", created_at: "x" },
    });
    render(<StaffPage />, { wrapper });
    await userEvent.type(await screen.findByLabelText("Nickname"), "@nuova.mod");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(writes()[0]).toEqual({
      url: "http://localhost:8000/v1/admin/staff/nuova.mod",
      method: "PUT",
      body: { role: "moderator" },
    });
  });
});
