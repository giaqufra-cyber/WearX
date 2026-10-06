"use client";

import type { AdminStyle, AdminStyleCreate, AdminStyleUpdate } from "@wearx/api-types";
import { type FormEvent, useState } from "react";

import { errorText } from "@/lib/api";
import { slugify } from "@/lib/format";
import { useStaffMutation, useStaffQuery } from "@/lib/queries";

type Draft = {
  slug: string;
  name: string;
  tagline: string;
  tone: string;
  min_age_band: "16_17" | "18_plus";
  active_from: string;
  active_until: string;
  sort_order: string;
  is_active: boolean;
};

const EMPTY: Draft = {
  slug: "",
  name: "",
  tagline: "",
  tone: "#2A2A2E",
  min_age_band: "16_17",
  active_from: "",
  active_until: "",
  sort_order: "100",
  is_active: true,
};

function toDraft(s: AdminStyle): Draft {
  return {
    slug: s.slug,
    name: s.name,
    tagline: s.tagline,
    tone: s.tone,
    min_age_band: s.min_age_band,
    active_from: s.active_from ?? "",
    active_until: s.active_until ?? "",
    sort_order: String(s.sort_order),
    is_active: s.is_active,
  };
}

function fields(d: Draft): AdminStyleUpdate {
  return {
    name: d.name,
    tagline: d.tagline,
    tone: d.tone.toUpperCase(),
    min_age_band: d.min_age_band,
    active_from: d.active_from || null,
    active_until: d.active_until || null,
    sort_order: Number(d.sort_order) || 0,
    is_active: d.is_active,
  };
}

/** Stili: creare, modificare, stagionalità, età minima, spegnere (solo admin). */
export default function StylesPage() {
  const styles = useStaffQuery<AdminStyle[]>("/v1/admin/styles");
  const [editing, setEditing] = useState<Draft | null>(null);
  const [isNew, setIsNew] = useState(false);
  const create = useStaffMutation<AdminStyleCreate, AdminStyle>("POST", () => "/v1/admin/styles");
  const update = useStaffMutation<AdminStyleUpdate & { slug: string }, AdminStyle>(
    "PATCH",
    (b) => `/v1/admin/styles/${b.slug}`,
    ({ slug: _slug, ...rest }) => rest,
  );
  const mutation = isNew ? create : update;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!editing) return;
    const done = { onSuccess: () => setEditing(null) };
    if (isNew) create.mutate({ ...fields(editing), slug: editing.slug } as AdminStyleCreate, done);
    else update.mutate({ ...fields(editing), slug: editing.slug }, done);
  };

  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Catalogo</div>
          <h1>Stili</h1>
        </div>
        <button
          className="btn primary"
          type="button"
          onClick={() => {
            setIsNew(true);
            setEditing(EMPTY);
          }}
        >
          Nuovo stile
        </button>
      </div>

      {editing ? (
        <form className="card" onSubmit={submit} style={{ display: "grid", gap: 12, marginBottom: 24 }} aria-label="Modifica stile">
          <h2>{isNew ? "Nuovo stile" : `Modifica ${editing.name}`}</h2>
          <div className="decide">
            <label className="field">
              <span>Nome</span>
              <input
                className="input"
                value={editing.name}
                onChange={(e) =>
                  setEditing({ ...editing, name: e.target.value, slug: isNew ? slugify(e.target.value) : editing.slug })
                }
                required
                maxLength={40}
              />
            </label>
            <label className="field">
              <span>Slug (indirizzo, non si cambia dopo)</span>
              <input className="input" value={editing.slug} disabled={!isNew} onChange={(e) => setEditing({ ...editing, slug: e.target.value })} required pattern="[a-z0-9\-]{2,40}" />
            </label>
          </div>
          <label className="field">
            <span>Descrizione breve</span>
            <input className="input" value={editing.tagline} onChange={(e) => setEditing({ ...editing, tagline: e.target.value })} required maxLength={90} />
          </label>
          <div className="decide" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
            <label className="field">
              <span>Colore</span>
              <input className="input" type="color" value={editing.tone} onChange={(e) => setEditing({ ...editing, tone: e.target.value.toUpperCase() })} />
            </label>
            <label className="field">
              <span>Età minima</span>
              <select className="input" value={editing.min_age_band} onChange={(e) => setEditing({ ...editing, min_age_band: e.target.value as Draft["min_age_band"] })}>
                <option value="16_17">Tutti (16+)</option>
                <option value="18_plus">Solo 18+</option>
              </select>
            </label>
            <label className="field">
              <span>Dal (stagionale)</span>
              <input className="input" type="date" value={editing.active_from} onChange={(e) => setEditing({ ...editing, active_from: e.target.value })} />
            </label>
            <label className="field">
              <span>Al (stagionale)</span>
              <input className="input" type="date" value={editing.active_until} onChange={(e) => setEditing({ ...editing, active_until: e.target.value })} />
            </label>
          </div>
          <div className="decide">
            <label className="field">
              <span>Ordine (più basso = prima)</span>
              <input className="input" type="number" min={0} max={10000} value={editing.sort_order} onChange={(e) => setEditing({ ...editing, sort_order: e.target.value })} />
            </label>
            <label className="field" style={{ alignContent: "end" }}>
              <span>Visibile nell&apos;app</span>
              <select className="input" value={editing.is_active ? "1" : "0"} onChange={(e) => setEditing({ ...editing, is_active: e.target.value === "1" })}>
                <option value="1">Sì</option>
                <option value="0">No (spento)</option>
              </select>
            </label>
          </div>
          <div className="actions-row">
            <button className="btn primary" type="submit" disabled={mutation.isPending}>
              Salva
            </button>
            <button className="btn" type="button" onClick={() => setEditing(null)}>
              Annulla
            </button>
          </div>
          {mutation.isError ? <p className="error">{errorText(mutation.error)}</p> : null}
        </form>
      ) : null}

      {styles.isError ? <p className="error">{errorText(styles.error)}</p> : null}
      <table className="table">
        <thead>
          <tr>
            <th>Stile</th>
            <th>Età</th>
            <th>Stagione</th>
            <th>Membri</th>
            <th>Fit 7 gg</th>
            <th>Stato</th>
            <th>
                <span className="sr-only">Azioni</span>
              </th>
          </tr>
        </thead>
        <tbody>
          {styles.data?.map((s) => (
            <tr key={s.slug}>
              <td>
                <span className="swatch" style={{ background: s.tone }} />
                <strong style={{ fontFamily: "var(--font-display)", fontSize: 16 }}>{s.name}</strong>
                <div className="muted">{s.tagline}</div>
              </td>
              <td>{s.min_age_band === "18_plus" ? "18+" : "16+"}</td>
              <td className="muted">{s.active_from || s.active_until ? `${s.active_from ?? "…"} → ${s.active_until ?? "…"}` : "sempre"}</td>
              <td>{s.members}</td>
              <td>{s.posts_7d}</td>
              <td>{s.is_active ? <span className="chip ok">attivo</span> : <span className="chip">spento</span>}</td>
              <td>
                <button
                  className="btn"
                  type="button"
                  onClick={() => {
                    setIsNew(false);
                    setEditing(toDraft(s));
                  }}
                >
                  Modifica
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
