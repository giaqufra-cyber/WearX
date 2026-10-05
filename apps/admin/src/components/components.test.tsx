import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import QueuePage from "@/app/queue/page";
import { Photo, pickVariant } from "@/components/Photo";

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ token: "tok", me: { role: "moderator", nickname: "mod" } }) }));
vi.mock("next/link", () => ({ default: ({ href, children }: { href: string; children: ReactNode }) => <a href={href}>{children}</a> }));

const QUEUE = [
  {
    target_type: "post",
    target_id: "p0",
    priority: 0,
    reasons: { minor_safety: 1 },
    reports: 1,
    automated: false,
    first_at: "2026-10-05T08:00:00Z",
    due_at: "2026-10-05T09:00:00Z",
    overdue: true,
    subject: "anna",
    subject_status: "active",
    post: null,
    details: ["sembra una ragazzina"],
  },
  {
    target_type: "profile",
    target_id: "u2",
    priority: 2,
    reasons: { spam: 2 },
    reports: 2,
    automated: false,
    first_at: "2026-10-05T08:00:00Z",
    due_at: "2026-10-08T08:00:00Z",
    overdue: false,
    subject: "spammer",
    subject_status: "active",
    post: null,
    details: [],
  },
];

const POST = {
  id: "p0",
  status: "hidden_moderation",
  author: "anna",
  author_status: "active",
  minor_author: false,
  style: "Galà",
  caption: "Serata",
  created_at: "2026-10-05T07:00:00Z",
  media: [{ position: 0, width: 1080, height: 1350, blurhash: "x", urls: { variants: { "320": "https://cdn/320", "640": "https://cdn/640" }, expires_at: "x" } }],
  items: [],
  vote_count: 0,
  average: null,
  reports: [],
};

let fetchMock: ReturnType<typeof vi.fn>;

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

beforeEach(() => {
  fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const json = (body: unknown, status = 200) =>
      new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
    if (url.includes("/v1/admin/reports/queue")) return json(QUEUE);
    if (url.includes("/v1/admin/posts/p0")) return json(POST);
    if (url.includes("/v1/admin/reports/decide") && init?.method === "POST")
      return json({ actions: ["a1"], sanction: "ban", resolved_reports: 1 });
    return json({ code: "x", title: "inatteso" }, 500);
  });
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("Foto", () => {
  test("variante e sfocatura finché non si sceglie di guardare", async () => {
    expect(pickVariant({ "320": "a", "640": "b", "1080": "c" }, 600)).toBe("b");
    expect(pickVariant({ "320": "a" }, 1000)).toBe("a");
    const onReveal = vi.fn();
    render(<Photo media={POST.media[0]!} revealed={false} onReveal={onReveal} warning="Attenzione" />);
    expect(screen.getByAltText("Foto sfocata")).toBeTruthy();
    expect(screen.getByText("Attenzione")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /Mostra/ }));
    expect(onReveal).toHaveBeenCalled();
  });
});

describe("Coda", () => {
  test("P0 in cima, dettaglio con foto sfocata, decisione da tastiera", async () => {
    render(<QueuePage />, { wrapper });
    const list = await screen.findByRole("listbox", { name: "Segnalazioni" });
    const options = within(list).getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]!.getAttribute("aria-selected")).toBe("true");
    expect(within(options[0]!).getByText("Minore in pericolo")).toBeTruthy();
    expect(within(options[0]!).getByText(/in ritardo/)).toBeTruthy();

    expect(await screen.findByText("Serata")).toBeTruthy();
    expect(screen.getByText("Possibile materiale illegale: guarda solo se serve")).toBeTruthy();
    expect(screen.getByText("sembra una ragazzina")).toBeTruthy();
    // Il fit è già nascosto in automatico: si può renderlo visibile, non nasconderlo di nuovo.
    expect(screen.getByRole("button", { name: /Rendi visibile/ })).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Nascondi/ })).toBeNull();
    expect((screen.getByLabelText("Sanzione per l'autore") as HTMLSelectElement).value).toBe("auto");

    await userEvent.keyboard("v");
    expect(screen.getByAltText("Foto del fit")).toBeTruthy();
    // "r" chiede conferma: la prima pressione non invia nulla.
    await userEvent.keyboard("r");
    expect(screen.getByRole("button", { name: /Conferma rimozione/ })).toBeTruthy();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("decide"))).toBe(false);
    await userEvent.keyboard("r");
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url).includes("decide"))).toBe(true));
    const [, init] = fetchMock.mock.calls.find(([url]) => String(url).includes("decide"))!;
    expect(JSON.parse(String(init.body))).toEqual({
      target_type: "post",
      target_id: "p0",
      decision: "remove",
      sanction: "auto",
      ground: "minor_safety",
      note: null,
    });
    expect(init.headers.Authorization).toBe("Bearer tok");
    expect(await screen.findByRole("status")).toBeTruthy();
  });

  test("profilo: si archivia o si sanziona, niente nascondi/rimuovi; le lettere nella nota non sono scorciatoie", async () => {
    render(<QueuePage />, { wrapper });
    const list = await screen.findByRole("listbox", { name: "Segnalazioni" });
    await userEvent.click(within(list).getAllByRole("option")[1]!);
    expect(await screen.findByText("Profilo @spammer")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Rimuovi/ })).toBeNull();
    expect((screen.getByRole("button", { name: "Sanziona" }) as HTMLButtonElement).disabled).toBe(true);
    await userEvent.type(screen.getByLabelText(/Nota interna/), "aaa rrr");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("decide"))).toBe(false);
  });
});
