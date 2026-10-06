import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import AppealsPage from "@/app/appeals/page";
import DomainsPage from "@/app/domains/page";
import FeedbackPage from "@/app/feedback/page";
import VotesPage from "@/app/votes/page";
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

  test("dominio bloccato: dominio e motivo; sblocco con conferma", async () => {
    serve({
      "GET http://localhost:8000/v1/admin/blocked-domains": [
        { domain: "falso.com", reason: "phishing", created_at: "2026-10-05T10:00:00Z", links: 3 },
      ],
      "POST http://localhost:8000/v1/admin/blocked-domains": {
        domain: "truffa.it",
        reason: "imita un marchio",
        created_at: "2026-10-05T11:00:00Z",
        links: 2,
      },
      "DELETE http://localhost:8000/v1/admin/blocked-domains/falso.com": null,
    });
    render(<DomainsPage />, { wrapper });
    expect(await screen.findByText("falso.com")).toBeTruthy();
    await userEvent.type(screen.getByLabelText("Dominio"), " truffa.it ");
    await userEvent.type(screen.getByLabelText("Motivo"), "imita un marchio");
    await userEvent.click(screen.getByRole("button", { name: "Blocca" }));
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(writes()[0]!.body).toEqual({ domain: "truffa.it", reason: "imita un marchio" });
    expect(await screen.findByText("truffa.it bloccato · 2 link fermati")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Sblocca" }));
    expect(writes()).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Conferma sblocco" }));
    await waitFor(() => expect(writes()).toHaveLength(2));
    expect(writes()[1]).toEqual({
      url: "http://localhost:8000/v1/admin/blocked-domains/falso.com",
      method: "DELETE",
      body: undefined,
    });
  });

  test("voti sospetti: pseudonimo, spiegazione, ripristino con conferma", async () => {
    serve({
      "GET http://localhost:8000/v1/admin/vote-flags": [
        {
          id: 7,
          rule: "author_burst",
          voter: "a1b2c3d4",
          author: "giulia.rossi",
          votes_affected: 9,
          detail: { votes: 9, scores: [100, 100], hours: 24 },
          detected_at: "2026-10-05T19:05:00Z",
          expires_at: "2026-11-04T19:05:00Z",
          lifted_at: null,
          active: true,
        },
        {
          id: 6,
          rule: "same_score",
          voter: "ffee0011",
          author: null,
          votes_affected: 41,
          detail: { votes: 41, scores: [69, 71], days: 7 },
          detected_at: "2026-10-04T19:05:00Z",
          expires_at: "2026-11-03T19:05:00Z",
          lifted_at: "2026-10-05T08:00:00Z",
          active: false,
        },
      ],
      "POST http://localhost:8000/v1/admin/vote-flags/7/lift": null,
    });
    render(<VotesPage />, { wrapper });
    expect(await screen.findByText("Spinta mirata")).toBeTruthy();
    expect(screen.getByText("9 voti in 24 ore ai fit di @giulia.rossi, tutti 100")).toBeTruthy();
    expect(screen.getByText("41 voti in 7 giorni, sempre tra 69 e 71")).toBeTruthy();
    expect(screen.getByText("#a1b2c3d4")).toBeTruthy();
    expect(screen.getByText("Ripristinato")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Ripristina i voti" })).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Ripristina i voti" }));
    expect(writes()).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Conferma ripristino" }));
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(writes()[0]!.url).toBe("http://localhost:8000/v1/admin/vote-flags/7/lift");
  });

  test("feedback: messaggio, contesto, nota e stato nel corpo", async () => {
    const item = {
      id: "f1",
      author: "giulia.rossi",
      kind: "bug",
      message: "Il voto non parte\nquando tocco due volte",
      app_version: "0.1.0",
      platform: "ios",
      os_version: "18.6",
      screen: "/post/[id]",
      status: "new",
      staff_note: null,
      created_at: "2026-10-06T08:00:00Z",
      updated_at: "2026-10-06T08:00:00Z",
    };
    serve({
      "GET http://localhost:8000/v1/admin/feedback?status=open": { items: [item], counts: { new: 1, seen: 0, done: 3 } },
      "PATCH http://localhost:8000/v1/admin/feedback/f1": { ...item, status: "done" },
    });
    render(<FeedbackPage />, { wrapper });
    expect(await screen.findByText(/Il voto non parte/)).toBeTruthy();
    expect(screen.getByText("WearX 0.1.0 · iOS 18.6 · da /post/[id]")).toBeTruthy();
    expect(screen.getByRole("radio", { name: "Da gestire (1)" })).toBeTruthy();
    await userEvent.type(screen.getByRole("textbox"), "Corretto nella 0.1.1");
    await userEvent.click(screen.getByRole("button", { name: "Risolto" }));
    await waitFor(() => expect(writes()).toHaveLength(1));
    expect(writes()[0]).toMatchObject({
      method: "PATCH",
      url: "http://localhost:8000/v1/admin/feedback/f1",
      body: { status: "done", staff_note: "Corretto nella 0.1.1" },
    });
  });
});
