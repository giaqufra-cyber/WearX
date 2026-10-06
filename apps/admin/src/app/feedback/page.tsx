"use client";

import type { Schemas } from "@wearx/api-types";
import Link from "next/link";
import { useState } from "react";

import { errorText } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useStaffMutation, useStaffQuery } from "@/lib/queries";

type Page = Schemas["FeedbackPage"];
type Item = Schemas["AdminFeedback"];
type State = "open" | "done" | "all";

const KIND: Record<Item["kind"], string> = { bug: "Non funziona", idea: "Idea", other: "Altro" };
const STATUS: Record<Item["status"], { label: string; className: string }> = {
  new: { label: "Nuovo", className: "chip p0" },
  seen: { label: "Visto", className: "chip p1" },
  done: { label: "Risolto", className: "chip ok" },
};
const SYSTEM: Record<string, string> = { ios: "iOS", android: "Android", web: "Web" };

/**
 * Messaggi dei tester ("Segnala un problema" nell'app, seduta 25). Si segnano come visti o
 * risolti, con una nota per gli altri dello staff; ogni cambio finisce nel registro.
 */
export default function FeedbackPage() {
  const [state, setState] = useState<State>("open");
  const page = useStaffQuery<Page>(`/v1/admin/feedback?status=${state}`);
  const items = page.data?.items ?? [];
  const counts = page.data?.counts;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Beta</div>
          <h1>Feedback</h1>
        </div>
        <div className="actions-row" role="radiogroup" aria-label="Quali messaggi">
          {(
            [
              ["open", `Da gestire${counts ? ` (${counts.new + counts.seen})` : ""}`],
              ["done", "Risolti"],
              ["all", "Tutti"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={state === value}
              className={`btn${state === value ? " inverse" : ""}`}
              onClick={() => setState(value)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <p className="muted" style={{ marginTop: -12, marginBottom: 20 }}>
        Con il messaggio arrivano solo versione dell&apos;app, sistema e schermata di partenza. Per rispondere a chi
        scrive non c&apos;è (ancora) un canale: annota qui cosa è stato fatto.
      </p>
      {page.isError ? <p className="error">{errorText(page.error)}</p> : null}
      {page.isSuccess && items.length === 0 ? <div className="card empty">Nessun messaggio.</div> : null}
      <div className="stack">
        {items.map((item) => (
          <FeedbackCard key={item.id} item={item} />
        ))}
      </div>
    </>
  );
}

function FeedbackCard({ item }: { item: Item }) {
  const [note, setNote] = useState(item.staff_note ?? "");
  const save = useStaffMutation<{ status: Item["status"] }>(
    "PATCH",
    () => `/v1/admin/feedback/${item.id}`,
    (body) => ({ status: body.status, staff_note: note.trim() || null }),
  );
  const status = STATUS[item.status];
  return (
    <article className="card" aria-label={`${KIND[item.kind]} da @${item.author}`}>
      <div className="actions-row" style={{ justifyContent: "space-between" }}>
        <div>
          <strong>{KIND[item.kind]}</strong>{" "}
          <span className="muted">
            da <Link href={`/users/${item.author}`}>@{item.author}</Link> · {dateTime(item.created_at)}
          </span>
        </div>
        <span className={status.className}>{status.label}</span>
      </div>
      <p style={{ whiteSpace: "pre-wrap", margin: "12px 0" }}>{item.message}</p>
      <p className="mono muted">
        WearX {item.app_version} · {SYSTEM[item.platform] ?? item.platform}
        {item.os_version ? ` ${item.os_version}` : ""}
        {item.screen ? ` · da ${item.screen}` : ""}
      </p>
      <label className="field" style={{ marginTop: 12 }}>
        <span className="mono">Nota dello staff</span>
        <input
          className="input"
          value={note}
          maxLength={500}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Es. corretto nella 0.1.1, idea per dopo la beta"
        />
      </label>
      {save.error ? <p className="error">{errorText(save.error)}</p> : null}
      <div className="actions-row" style={{ marginTop: 12 }}>
        {item.status === "new" ? (
          <button className="btn" type="button" disabled={save.isPending} onClick={() => save.mutate({ status: "seen" })}>
            Segna come visto
          </button>
        ) : null}
        {item.status !== "done" ? (
          <button
            className="btn inverse"
            type="button"
            disabled={save.isPending}
            onClick={() => save.mutate({ status: "done" })}
          >
            Risolto
          </button>
        ) : (
          <button className="btn" type="button" disabled={save.isPending} onClick={() => save.mutate({ status: "seen" })}>
            Riapri
          </button>
        )}
      </div>
    </article>
  );
}
