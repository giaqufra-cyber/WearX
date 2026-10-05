"use client";

import type { AppealDecision, AppealItem } from "@wearx/api-types";
import Link from "next/link";
import { useState } from "react";

import { errorText } from "@/lib/api";
import { ACTIONS, dateTime } from "@/lib/format";
import { useStaffMutation, useStaffQuery } from "@/lib/queries";

/** Reclami (art. 20 DSA): li decide un moderatore diverso da chi ha preso la decisione. */
export default function AppealsPage() {
  const appeals = useStaffQuery<AppealItem[]>("/v1/admin/appeals");
  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Moderazione</div>
          <h1>Reclami</h1>
        </div>
      </div>
      {appeals.isError ? <p className="error">{errorText(appeals.error)}</p> : null}
      {appeals.data?.length === 0 ? <div className="card empty">Nessun reclamo da decidere.</div> : null}
      <div style={{ display: "grid", gap: 12 }}>
        {appeals.data?.map((a) => (
          <AppealCard key={a.id} appeal={a} />
        ))}
      </div>
    </>
  );
}

function AppealCard({ appeal }: { appeal: AppealItem }) {
  const [note, setNote] = useState("");
  const decide = useStaffMutation<AppealDecision & { id: string }>(
    "POST",
    (b) => `/v1/admin/appeals/${b.id}`,
    ({ decision, note: text }) => ({ decision, note: text }),
  );
  const send = (decision: AppealDecision["decision"]) => decide.mutate({ id: appeal.id, decision, note: note.trim() });
  return (
    <article className="card" style={{ display: "grid", gap: 12 }} aria-label={`Reclamo di @${appeal.nickname ?? "?"}`}>
      <div className="queue-row">
        <span className="chip">{ACTIONS[appeal.action.action] ?? appeal.action.action}</span>
        <span className="chip">{appeal.action.automated ? "automatica" : "di un moderatore"}</span>
        <span className="muted">
          {appeal.nickname ? <Link href={`/users/${appeal.nickname}`}>@{appeal.nickname}</Link> : "account eliminato"} ·{" "}
          {dateTime(appeal.created_at)}
        </span>
      </div>
      <div>
        <div className="mono">Il reclamo</div>
        <p style={{ margin: "6px 0 0", fontSize: 16 }}>{appeal.text}</p>
      </div>
      <div>
        <div className="mono">La decisione contestata</div>
        <p className="muted" style={{ margin: "6px 0 0" }}>
          {appeal.action.statement}
        </p>
      </div>
      <label className="field">
        <span>Risposta per la persona (obbligatoria)</span>
        <textarea className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
      </label>
      <div className="actions-row">
        <button className="btn primary" type="button" disabled={note.trim().length < 2 || decide.isPending} onClick={() => send("reverse")}>
          Accogli e annulla la decisione
        </button>
        <button className="btn" type="button" disabled={note.trim().length < 2 || decide.isPending} onClick={() => send("uphold")}>
          Respingi
        </button>
      </div>
      {decide.isError ? <p className="error">{errorText(decide.error)}</p> : null}
    </article>
  );
}
