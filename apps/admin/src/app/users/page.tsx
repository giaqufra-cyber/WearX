"use client";

import type { AdminUserRow } from "@wearx/api-types";
import Link from "next/link";
import { useDeferredValue, useState } from "react";

import { errorText } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useStaffQuery } from "@/lib/queries";

/** Persone: ricerca per inizio del nickname (solo staff). */
export default function UsersPage() {
  const [q, setQ] = useState("");
  const query = useDeferredValue(q.trim().toLowerCase());
  const users = useStaffQuery<AdminUserRow[]>(query ? `/v1/admin/users?q=${encodeURIComponent(query)}` : null);
  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Persone</div>
          <h1>Cerca una persona</h1>
        </div>
      </div>
      <label className="field" style={{ maxWidth: 420, marginBottom: 20 }}>
        <span>Nickname (anche solo l&apos;inizio)</span>
        <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="es. giulia" autoFocus />
      </label>
      {users.isError ? <p className="error">{errorText(users.error)}</p> : null}
      {users.data ? (
        <table className="table">
          <thead>
            <tr>
              <th>Nickname</th>
              <th>Stato</th>
              <th>Età</th>
              <th>Tipo</th>
              <th>Fit</th>
              <th>Iscritto</th>
            </tr>
          </thead>
          <tbody>
            {users.data.map((u) => (
              <tr key={u.nickname}>
                <td>
                  <Link href={`/users/${u.nickname}`}>@{u.nickname}</Link>
                </td>
                <td>{u.status === "active" ? "attivo" : u.status === "suspended" ? <span className="error">sospeso</span> : u.status}</td>
                <td>{u.age_band === "16_17" ? "16-17" : "18+"}</td>
                <td>{u.account_type}</td>
                <td>{u.posts}</td>
                <td className="muted">{dateTime(u.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      {users.data?.length === 0 ? <p className="muted">Nessun nickname inizia così.</p> : null}
    </>
  );
}
