"use client";

import type { ModerationAction, SanctionRequest, UserCase } from "@wearx/api-types";
import { useParams } from "next/navigation";
import { useState } from "react";

import { errorText } from "@/lib/api";
import { ACCOUNT_TYPE, ACTIONS, APPEAL_STATUS, GROUNDS, dateTime } from "@/lib/format";
import { useStaffMutation, useStaffQuery } from "@/lib/queries";

const NEXT: Record<string, string> = { warn: "avviso", limit_posting: "pubblicazione sospesa 7 giorni", ban: "chiusura" };

/** Scheda di una persona: stato, sanzioni ricevute, storico delle decisioni. */
export default function UserPage() {
  const { nickname } = useParams<{ nickname: string }>();
  const user = useStaffQuery<UserCase>(`/v1/admin/users/${encodeURIComponent(nickname)}`);
  const [ground, setGround] = useState("other");
  const [note, setNote] = useState("");
  const sanction = useStaffMutation<SanctionRequest, ModerationAction>("POST", () => `/v1/admin/users/${nickname}/sanction`);
  const reinstate = useStaffMutation<{ note: string }>("POST", () => `/v1/admin/users/${nickname}/reinstate`);

  if (user.isError) return <p className="error">{errorText(user.error)}</p>;
  const u = user.data;
  if (!u) return <p className="muted">Caricamento…</p>;
  const restricted = u.status === "suspended" || (u.posting_blocked_until && new Date(u.posting_blocked_until) > new Date());

  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Persona</div>
          <h1>@{u.nickname}</h1>
        </div>
        <div className="queue-row">
          <span className={`chip${u.status === "suspended" ? " late" : " ok"}`}>{u.status === "suspended" ? "sospeso" : "attivo"}</span>
          <span className="chip">{u.age_band === "16_17" ? "16-17 anni" : "18+"}</span>
          <span className="chip">{ACCOUNT_TYPE[u.account_type] ?? u.account_type}</span>
        </div>
      </div>
      <div className="grid-stats" style={{ gridTemplateColumns: "repeat(3, minmax(0,1fr))", marginBottom: 24 }}>
        <div className="card">
          <div className="mono">Sanzioni negli ultimi 12 mesi</div>
          <div className="stat-value">{u.strikes}</div>
        </div>
        <div className="card">
          <div className="mono">Prossima sanzione della scala</div>
          <div style={{ fontSize: 18, fontWeight: 700, marginTop: 14 }}>{NEXT[u.next_sanction] ?? u.next_sanction}</div>
        </div>
        <div className="card">
          <div className="mono">Segnalazioni aperte</div>
          <div className={`stat-value${u.open_reports ? " danger" : ""}`}>{u.open_reports}</div>
        </div>
      </div>
      {u.posting_blocked_until ? (
        <p className="muted">Non può pubblicare fino al {dateTime(u.posting_blocked_until)}.</p>
      ) : null}

      <div className="card" style={{ display: "grid", gap: 12, marginBottom: 24 }}>
        <h2>Intervieni</h2>
        <div className="decide">
          <label className="field">
            <span>Motivo</span>
            <select className="input" value={ground} onChange={(e) => setGround(e.target.value)}>
              {GROUNDS.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Nota interna</span>
            <input className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
          </label>
        </div>
        <div className="actions-row">
          {(["warn", "limit_posting", "ban"] as const).map((s) => (
            <button
              key={s}
              type="button"
              className={`btn${s === "ban" ? " danger" : ""}`}
              disabled={sanction.isPending}
              onClick={() => sanction.mutate({ sanction: s, ground, note: note.trim() || null })}
            >
              {s === "warn" ? "Avviso" : s === "limit_posting" ? "Sospendi la pubblicazione" : "Chiudi l'account"}
            </button>
          ))}
          {restricted ? (
            <button
              type="button"
              className="btn primary"
              disabled={note.trim().length < 2 || reinstate.isPending}
              onClick={() => reinstate.mutate({ note: note.trim() })}
              title="Serve una nota"
            >
              Riattiva
            </button>
          ) : null}
        </div>
        {sanction.isError || reinstate.isError ? <p className="error">{errorText(sanction.error ?? reinstate.error)}</p> : null}
      </div>

      <h2 style={{ marginBottom: 12 }}>Storico</h2>
      {u.actions.length === 0 ? <p className="muted">Nessuna decisione.</p> : null}
      <table className="table">
        <tbody>
          {u.actions.map((a) => (
            <tr key={a.id} className={a.reversed_at ? "reversed" : undefined}>
              <td style={{ width: 170 }} className="muted">
                {dateTime(a.created_at)}
              </td>
              <td style={{ width: 170 }}>
                <strong>{ACTIONS[a.action] ?? a.action}</strong>
                <div className="muted">{a.automated ? "automatica" : "moderatore"}</div>
              </td>
              <td>{a.statement}</td>
              <td style={{ width: 150 }}>
                <div className="stack-chips">
                  {a.reversed_at ? <span className="chip">annullata</span> : null}
                  {a.appeal_status ? <span className="chip">{APPEAL_STATUS[a.appeal_status] ?? a.appeal_status}</span> : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
