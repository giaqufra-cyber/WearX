"use client";

import type { AdminStats } from "@wearx/api-types";
import Link from "next/link";

import { errorText } from "@/lib/api";
import { useStaffQuery } from "@/lib/queries";

/** Panoramica: cosa c'è da fare adesso e come sta andando WearX oggi. */
export default function Overview() {
  const stats = useStaffQuery<AdminStats>("/v1/admin/stats", { refetchInterval: 60_000 });
  if (stats.isError) return <p className="error">{errorText(stats.error)}</p>;
  const s = stats.data;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Panoramica</div>
          <h1>Oggi su WearX</h1>
        </div>
        <Link className="btn primary" href="/queue">
          Apri la coda
        </Link>
      </div>
      <h2 style={{ marginBottom: 12 }}>Da fare</h2>
      <div className="grid-stats" style={{ marginBottom: 28 }}>
        <Stat label="P0 · minori, entro 1 ora" value={s?.reports.p0} tone={s?.reports.p0 ? "danger" : undefined} />
        <Stat label="P1 · entro 24 ore" value={s?.reports.p1} />
        <Stat label="In ritardo" value={s?.reports.overdue} tone={s?.reports.overdue ? "danger" : undefined} />
        <Stat label="Reclami aperti" value={s?.appeals_open} />
      </div>
      <h2 style={{ marginBottom: 12 }}>Attività</h2>
      <div className="grid-stats">
        <Stat label="Fit pubblicati oggi" value={s?.posts_today} tone="accent" />
        <Stat label="Voti oggi" value={s?.votes_today} />
        <Stat label="Persone · nuove in 7 giorni" value={s ? `${s.users} · ${s.users_new_7d}` : undefined} />
        <Stat label="Account sospesi" value={s?.suspended} />
      </div>
    </>
  );
}

function Stat({ label, value, tone }: { label: string; value: number | string | undefined; tone?: "accent" | "danger" }) {
  return (
    <div className="card" aria-label={`${label}: ${value ?? "…"}`}>
      <div className="mono">{label}</div>
      <div className={`stat-value${tone ? ` ${tone}` : ""}`}>{value ?? "…"}</div>
    </div>
  );
}
