"use client";

import type { AuditPage } from "@wearx/api-types";
import { useState } from "react";

import { errorText } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useStaffQuery } from "@/lib/queries";

const LABELS: Record<string, string> = {
  "moderation.decide": "Decisione su segnalazioni",
  "moderation.sanction": "Sanzione",
  "moderation.appeal": "Reclamo deciso",
  "moderation.view_user": "Scheda persona aperta",
  "admin.view_post": "Fit aperto",
  "admin.reinstate": "Riattivazione",
  "admin.style_create": "Stile creato",
  "admin.style_update": "Stile modificato",
  "admin.staff_set": "Ruolo staff",
  "admin.staff_remove": "Tolto dallo staff",
};

/** Registro di audit: ogni azione dello staff, non modificabile (solo admin). */
export default function AuditLogPage() {
  const [cursors, setCursors] = useState<number[]>([]);
  const cursor = cursors.at(-1);
  const page = useStaffQuery<AuditPage>(`/v1/admin/audit?limit=50${cursor ? `&cursor=${cursor}` : ""}`);
  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Controllo</div>
          <h1>Registro di audit</h1>
        </div>
        <div className="actions-row">
          <button className="btn" type="button" disabled={cursors.length === 0} onClick={() => setCursors(cursors.slice(0, -1))}>
            Più recenti
          </button>
          <button
            className="btn"
            type="button"
            disabled={!page.data?.next_cursor}
            onClick={() => page.data?.next_cursor && setCursors([...cursors, page.data.next_cursor])}
          >
            Più vecchi
          </button>
        </div>
      </div>
      {page.isError ? <p className="error">{errorText(page.error)}</p> : null}
      <table className="table">
        <thead>
          <tr>
            <th>Quando</th>
            <th>Chi</th>
            <th>Azione</th>
            <th>Su</th>
            <th>Dettagli</th>
          </tr>
        </thead>
        <tbody>
          {page.data?.items.map((r) => (
            <tr key={r.id}>
              <td className="muted" style={{ whiteSpace: "nowrap" }}>
                {dateTime(r.ts)}
              </td>
              <td>@{r.staff ?? "—"}</td>
              <td>{LABELS[r.action] ?? r.action}</td>
              <td className="mono" style={{ textTransform: "none" }}>
                {r.target}
              </td>
              <td className="muted">
                {r.details && Object.keys(r.details).length ? (
                  <code style={{ fontSize: 12 }}>{JSON.stringify(r.details)}</code>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
