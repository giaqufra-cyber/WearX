"use client";

import type { AdminStyleProposal } from "@wearx/api-types";
import { useState } from "react";

import { errorText } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useStaffMutation, useStaffQuery } from "@/lib/queries";

const STATUS = [
  { value: "open", label: "Aperte" },
  { value: "approved", label: "Diventate stili" },
  { value: "rejected", label: "Respinte" },
] as const;

const CATEGORY: Record<string, string> = {
  stili: "Stili",
  sport: "Sport",
  accessori: "Accessori",
  beauty: "Beauty",
  sottoculture: "Sottoculture",
  occasioni: "Occasioni",
};

/**
 * Stili proposti dagli utenti (seduta 30). Alla soglia di richieste lo stile si attiva da solo;
 * qui si respingono le proposte aperte che non vanno (doppioni, nomi fuori luogo). Uno stile già
 * nato si spegne dalla pagina Stili.
 */
export default function ProposalsPage() {
  const [status, setStatus] = useState<(typeof STATUS)[number]["value"]>("open");
  const list = useStaffQuery<AdminStyleProposal[]>(`/v1/admin/style-proposals?status=${status}`);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const reject = useStaffMutation<{ id: string; note: string }>(
    "POST",
    (b) => `/v1/admin/style-proposals/${b.id}/reject`,
    (b) => ({ note: b.note.trim() || null }),
  );

  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Community</div>
          <h1>Stili proposti</h1>
        </div>
        <label className="field" style={{ minWidth: 200 }}>
          <span>Mostra</span>
          <select className="input" value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
            {STATUS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {reject.error ? <p className="error">{errorText(reject.error)}</p> : null}
      {list.isSuccess && list.data.length === 0 ? <div className="card empty">Nessuna proposta.</div> : null}
      {list.data && list.data.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Categoria</th>
              <th>Richieste</th>
              <th>Proposto da</th>
              <th>Quando</th>
              <th>
                <span className="sr-only">Azioni</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {list.data.map((p) => (
              <tr key={p.id}>
                <td>
                  <strong>{p.name}</strong>
                  {p.tagline ? <div className="muted">{p.tagline}</div> : null}
                  {p.staff_note ? <div className="muted">Nota: {p.staff_note}</div> : null}
                </td>
                <td>{CATEGORY[p.category] ?? p.category}</td>
                <td>{p.supports}</td>
                <td>{p.proposer ? `@${p.proposer}` : "account cancellato"}</td>
                <td className="muted">{dateTime(p.created_at)}</td>
                <td>
                  {p.status === "approved" && p.style ? <span className="chip">Stile: {p.style}</span> : null}
                  {p.status === "open" && rejecting !== p.id ? (
                    <button className="btn" type="button" onClick={() => setRejecting(p.id)}>
                      Respingi
                    </button>
                  ) : null}
                  {p.status === "open" && rejecting === p.id ? (
                    <div style={{ display: "grid", gap: 6 }}>
                      <input
                        className="input"
                        aria-label={`Motivo per ${p.name}`}
                        placeholder="Motivo (facoltativo)"
                        value={note}
                        maxLength={300}
                        onChange={(e) => setNote(e.target.value)}
                      />
                      <button
                        className="btn danger"
                        type="button"
                        disabled={reject.isPending}
                        onClick={() =>
                          reject.mutate(
                            { id: p.id, note },
                            {
                              onSuccess: () => {
                                setRejecting(null);
                                setNote("");
                              },
                            },
                          )
                        }
                      >
                        Conferma: respingi
                      </button>
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </>
  );
}
