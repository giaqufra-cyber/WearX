"use client";

import type { VoteFlag } from "@wearx/api-types";
import { useState } from "react";

import { errorText } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useStaffMutation, useStaffQuery } from "@/lib/queries";

function votes(f: VoteFlag): string {
  const n = Number(f.detail.votes ?? 0);
  return n === 1 ? "1 voto" : `${n} voti`;
}

const RULES: Record<VoteFlag["rule"], { label: string; text: (f: VoteFlag) => string }> = {
  same_score: {
    label: "Stesso voto ovunque",
    text: (f) => `${votes(f)} in ${String(f.detail.days ?? 7)} giorni, sempre ${scores(f)}`,
  },
  author_burst: {
    label: "Spinta mirata",
    text: (f) => `${votes(f)} in 24 ore ai fit di @${f.author ?? "?"}, tutti ${scores(f)}`,
  },
};

function scores(f: VoteFlag): string {
  const [lo, hi] = (f.detail.scores as number[] | undefined) ?? [];
  return lo === hi ? String(lo) : `tra ${String(lo)} e ${String(hi)}`;
}

/**
 * Voti sospetti trovati dal controllo orario: i voti del votante (o solo quelli verso un autore)
 * non contano più nelle medie. Chi ha votato non se ne accorge. Se è un falso positivo, si
 * ripristinano: medie ricalcolate al prossimo aggiornamento orario.
 */
export default function VotesPage() {
  const flags = useStaffQuery<VoteFlag[]>("/v1/admin/vote-flags");
  const [confirm, setConfirm] = useState<number | null>(null);
  const lift = useStaffMutation<{ id: number }>("POST", (b) => `/v1/admin/vote-flags/${b.id}/lift`);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Anti-abuso</div>
          <h1>Voti sospetti</h1>
        </div>
      </div>
      <p className="muted" style={{ marginBottom: 20 }}>
        Il votante è indicato solo con uno pseudonimo: lo staff non vede chi è. I voti neutralizzati restano visibili a
        chi li ha dati ma non contano; il blocco dura 30 giorni per i voti nuovi. Ripristinare finisce nel registro.
      </p>
      {lift.error ? <p className="error">{errorText(lift.error)}</p> : null}
      {flags.isSuccess && flags.data.length === 0 ? <div className="card empty">Nessun voto sospetto.</div> : null}
      {flags.data && flags.data.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>Segnale</th>
              <th>Votante</th>
              <th>Voti</th>
              <th>Trovato</th>
              <th>Stato</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {flags.data.map((f) => (
              <tr key={f.id}>
                <td>
                  <strong>{RULES[f.rule].label}</strong>
                  <div className="muted">{RULES[f.rule].text(f)}</div>
                </td>
                <td className="mono">#{f.voter}</td>
                <td>{f.votes_affected}</td>
                <td className="muted">{dateTime(f.detected_at)}</td>
                <td>
                  {f.lifted_at ? (
                    <span className="chip">Ripristinato</span>
                  ) : f.active ? (
                    <span className="chip p0">Attivo</span>
                  ) : (
                    <span className="chip">Scaduto</span>
                  )}
                </td>
                <td>
                  {f.lifted_at ? null : confirm === f.id ? (
                    <button
                      className="btn"
                      type="button"
                      disabled={lift.isPending}
                      onClick={() => lift.mutate({ id: f.id }, { onSuccess: () => setConfirm(null) })}
                    >
                      Conferma ripristino
                    </button>
                  ) : (
                    <button className="btn" type="button" onClick={() => setConfirm(f.id)}>
                      Ripristina i voti
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </>
  );
}
