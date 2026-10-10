"use client";

import type { AdminPost, ModerationDecision, ModerationDecisionResult, QueueItem } from "@wearx/api-types";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Photo } from "@/components/Photo";
import { errorText } from "@/lib/api";
import { GROUNDS, POST_STATUS, PRIORITY_LABEL, REASONS, dueLabel, mainReason, queueCommand } from "@/lib/format";
import { useStaffMutation, useStaffQuery } from "@/lib/queries";

type Filter = "all" | "0" | "1" | "2";

/** Coda di moderazione: segnalazioni raggruppate per contenuto, priorità e scadenza. */
export default function QueuePage() {
  const [filter, setFilter] = useState<Filter>("all");
  const queue = useStaffQuery<QueueItem[]>(`/v1/admin/reports/queue${filter === "all" ? "" : `?priority=${filter}`}`, {
    refetchInterval: 30_000,
  });
  const items = useMemo(() => queue.data ?? [], [queue.data]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const keyOf = (i: QueueItem) => `${i.target_type}:${i.target_id}`;
  const index = Math.max(
    0,
    items.findIndex((i) => keyOf(i) === selectedKey),
  );
  const selected = items[index];
  const [message, setMessage] = useState<string | null>(null);

  const move = useCallback(
    (step: number) => {
      const next = items[Math.min(items.length - 1, Math.max(0, index + step))];
      if (next) setSelectedKey(keyOf(next));
    },
    [items, index],
  );

  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Moderazione</div>
          <h1>Coda</h1>
        </div>
        <div className="actions-row" role="radiogroup" aria-label="Priorità">
          {(["all", "0", "1", "2"] as const).map((f) => (
            <button
              key={f}
              type="button"
              role="radio"
              aria-checked={filter === f}
              className={`btn${filter === f ? " inverse" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f === "all" ? "Tutte" : PRIORITY_LABEL[Number(f)]}
            </button>
          ))}
        </div>
      </div>
      <p className="muted" style={{ marginTop: -12, marginBottom: 20 }}>
        Scorciatoie: <kbd>J</kbd>/<kbd>K</kbd> scorri · <kbd>V</kbd> mostra foto · <kbd>A</kbd> archivia · <kbd>N</kbd>{" "}
        nascondi · <kbd>R</kbd> rimuovi
      </p>
      {message ? (
        <p className="chip ok" role="status" style={{ marginBottom: 16 }}>
          {message}
        </p>
      ) : null}
      {queue.isError ? <p className="error">{errorText(queue.error)}</p> : null}
      {queue.isSuccess && items.length === 0 ? (
        <div className="card empty">Nessuna segnalazione aperta. Ottimo lavoro.</div>
      ) : null}
      {items.length > 0 ? (
        <div className="queue">
          <div className="queue-list" role="listbox" aria-label="Segnalazioni">
            {items.map((item) => (
              <QueueRow key={keyOf(item)} item={item} selected={item === selected} onSelect={() => setSelectedKey(keyOf(item))} />
            ))}
          </div>
          {selected ? (
            <QueueDetail
              key={keyOf(selected)}
              item={selected}
              onMove={move}
              onDone={(text) => {
                setMessage(text);
                const next = items[index + 1] ?? items[index - 1];
                setSelectedKey(next ? keyOf(next) : null);
              }}
            />
          ) : null}
        </div>
      ) : null}
    </>
  );
}

function QueueRow({ item, selected, onSelect }: { item: QueueItem; selected: boolean; onSelect: () => void }) {
  const reason = mainReason(item.reasons);
  return (
    <button type="button" role="option" aria-selected={selected} className="queue-item" onClick={onSelect}>
      <div className="queue-row">
        <span className={`chip p${item.priority}`}>{PRIORITY_LABEL[item.priority]}</span>
        <span className={`chip${item.overdue ? " late" : ""}`}>{dueLabel(item.due_at)}</span>
        {item.automated ? <span className="chip">automatica</span> : null}
      </div>
      <strong>{REASONS[reason] ?? reason}</strong>
      <span className="muted">
        {item.target_type === "post" ? "Fit" : item.target_type === "profile" ? "Profilo" : "Link"}
        {item.subject ? ` di @${item.subject}` : ""} · {item.reports} {item.reports === 1 ? "segnalazione" : "segnalazioni"}
      </span>
    </button>
  );
}

const SANCTIONS = [
  { value: "none", label: "Nessuna sanzione" },
  { value: "auto", label: "Scala automatica" },
  { value: "warn", label: "Avviso" },
  { value: "limit_posting", label: "Pubblicazione sospesa 7 giorni" },
  { value: "ban", label: "Chiusura dell'account" },
] as const;

function QueueDetail({ item, onMove, onDone }: { item: QueueItem; onMove: (step: number) => void; onDone: (message: string) => void }) {
  const post = useStaffQuery<AdminPost>(item.target_type === "post" ? `/v1/admin/posts/${item.target_id}` : null);
  const reason = mainReason(item.reasons);
  const [ground, setGround] = useState(GROUNDS.some((g) => g.value === reason) ? reason : "other");
  const [sanction, setSanction] = useState<ModerationDecision["sanction"]>(item.priority === 0 ? "auto" : "none");
  const [note, setNote] = useState("");
  const [revealed, setRevealed] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState(false);
  const decide = useStaffMutation<ModerationDecision, ModerationDecisionResult>("POST", () => "/v1/admin/reports/decide");
  const isPost = item.target_type === "post";
  const hidden = post.data?.status === "hidden_moderation";
  // Profilo: "rimuovi" toglie bio e foto profilo (seduta 27), se ce n'è almeno una.
  const canClearProfile = item.target_type === "profile" && Boolean(item.profile?.bio || item.profile?.avatar);

  const send = useCallback(
    (decision: ModerationDecision["decision"]) => {
      if (decision === "remove" && !confirmRemove) {
        setConfirmRemove(true);
        return;
      }
      decide.mutate(
        {
          target_type: item.target_type,
          target_id: item.target_id,
          decision,
          sanction: decision === "dismiss" ? "none" : sanction,
          ground,
          note: note.trim() || null,
        },
        {
          onSuccess: (result) =>
            onDone(
              decision === "dismiss"
                ? `Archiviata (${result.resolved_reports} segnalazioni chiuse).`
                : `Decisione salvata${result.sanction ? ` · sanzione: ${result.sanction}` : ""}.`,
            ),
        },
      );
    },
    [confirmRemove, decide, item, sanction, ground, note, onDone],
  );

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const command = queueCommand(event);
      if (!command || decide.isPending) return;
      event.preventDefault();
      if (command === "next") onMove(1);
      else if (command === "prev") onMove(-1);
      else if (command === "reveal") setRevealed(true);
      else if (command === "dismiss") send("dismiss");
      else if (command === "hide" && isPost) send("hide");
      else if (command === "remove" && isPost) send("remove");
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onMove, send, isPost, decide.isPending]);

  return (
    <section className="detail card" aria-label="Dettaglio della segnalazione">
      <div className="queue-row">
        <span className={`chip p${item.priority}`}>{PRIORITY_LABEL[item.priority]}</span>
        <span className={`chip${item.overdue ? " late" : ""}`}>{dueLabel(item.due_at)}</span>
        {Object.entries(item.reasons).map(([r, n]) => (
          <span key={r} className="chip">
            {REASONS[r] ?? r} · {n}
          </span>
        ))}
      </div>
      <div>
        <h2>{isPost ? (post.data?.caption ?? "Fit senza didascalia") : `Profilo @${item.subject ?? "?"}`}</h2>
        <p className="muted" style={{ margin: "6px 0 0" }}>
          {item.subject ? (
            <>
              di <Link href={`/users/${item.subject}`}>@{item.subject}</Link>
              {item.subject_status === "suspended" ? " · account sospeso" : ""}
            </>
          ) : null}
          {post.data ? ` · ${post.data.style} · ${POST_STATUS[post.data.status] ?? post.data.status}${post.data.minor_author ? " · autore 16-17" : ""}` : null}
        </p>
      </div>

      {isPost && post.data ? (
        <div className="photos">
          {post.data.media.map((m) => (
            <Photo
              key={m.position}
              media={m}
              revealed={revealed}
              onReveal={() => setRevealed(true)}
              warning={item.priority === 0 ? "Possibile materiale illegale: guarda solo se serve" : undefined}
            />
          ))}
        </div>
      ) : null}
      {isPost && post.isError ? <p className="error">{errorText(post.error)}</p> : null}

      {!isPost && item.profile ? (
        <div className="profile-preview">
          <div>
            <div className="mono">Bio</div>
            <p style={{ margin: "6px 0 0", whiteSpace: "pre-line" }}>{item.profile.bio ?? "Nessuna bio"}</p>
          </div>
          {item.profile.avatar ? (
            <div style={{ maxWidth: 220 }}>
              <div className="mono">Foto profilo</div>
              <Photo
                media={{ urls: item.profile.avatar }}
                revealed={revealed}
                onReveal={() => setRevealed(true)}
                warning={item.priority === 0 ? "Possibile materiale illegale: guarda solo se serve" : undefined}
              />
            </div>
          ) : (
            <p className="muted">Nessuna foto profilo.</p>
          )}
        </div>
      ) : null}

      {post.data && post.data.items.length > 0 ? (
        <div>
          <div className="mono">Capi</div>
          <ul className="details">
            {post.data.items.map((i) => (
              <li key={i.position}>
                {i.brand} — {i.name}
                {i.link ? ` · ${i.link.domain} (${i.link.status})` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {item.details.length > 0 ? (
        <div>
          <div className="mono">Cosa scrivono le segnalazioni</div>
          <ul className="details">
            {item.details.map((d, n) => (
              <li key={n}>{d}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="decide">
        <label className="field">
          <span>Motivo della decisione</span>
          <select className="input" value={ground} onChange={(e) => setGround(e.target.value)}>
            {GROUNDS.map((g) => (
              <option key={g.value} value={g.value}>
                {g.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Sanzione per l&apos;autore</span>
          <select className="input" value={sanction} onChange={(e) => setSanction(e.target.value as ModerationDecision["sanction"])}>
            {SANCTIONS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="field">
        <span>Nota interna (registro di audit)</span>
        <textarea className="input" value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} />
      </label>
      <div className="actions-row">
        <button className="btn" type="button" disabled={decide.isPending} onClick={() => send("dismiss")}>
          Archivia <kbd>A</kbd>
        </button>
        {isPost && !hidden ? (
          <button className="btn inverse" type="button" disabled={decide.isPending} onClick={() => send("hide")}>
            Nascondi <kbd>N</kbd>
          </button>
        ) : null}
        {isPost && hidden ? (
          <button className="btn" type="button" disabled={decide.isPending} onClick={() => send("restore")}>
            Rendi visibile
          </button>
        ) : null}
        {isPost ? (
          <button className="btn danger" type="button" disabled={decide.isPending} onClick={() => send("remove")}>
            {confirmRemove ? "Conferma rimozione" : "Rimuovi"} <kbd>R</kbd>
          </button>
        ) : null}
        {canClearProfile ? (
          <button className="btn danger" type="button" disabled={decide.isPending} onClick={() => send("remove")}>
            {confirmRemove ? "Conferma: togli bio e foto" : "Togli bio e foto"}
          </button>
        ) : null}
        {isPost ? null : (
          <button className="btn inverse" type="button" disabled={decide.isPending || sanction === "none"} onClick={() => send("none")}>
            Sanziona
          </button>
        )}
      </div>
      {confirmRemove ? (
        <p className="muted">
          {isPost
            ? "La rimozione cancella le foto e ne impedisce la ripubblicazione. Premi di nuovo per confermare."
            : "Bio e foto profilo vengono cancellate; la stessa foto non si potrà ricaricare. Premi di nuovo per confermare."}
        </p>
      ) : null}
      {decide.isError ? <p className="error">{errorText(decide.error)}</p> : null}
    </section>
  );
}
