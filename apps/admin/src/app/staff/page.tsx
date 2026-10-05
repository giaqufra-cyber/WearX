"use client";

import type { StaffRow } from "@wearx/api-types";
import { useState } from "react";

import { errorText } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useStaffMutation, useStaffQuery } from "@/lib/queries";

/** Chi fa parte dello staff (solo admin). Serve sempre almeno un amministratore. */
export default function StaffPage() {
  const staff = useStaffQuery<StaffRow[]>("/v1/admin/staff");
  const [nickname, setNickname] = useState("");
  const [role, setRole] = useState<StaffRow["role"]>("moderator");
  const put = useStaffMutation<{ nickname: string; role: StaffRow["role"] }>(
    "PUT",
    (b) => `/v1/admin/staff/${encodeURIComponent(b.nickname)}`,
    (b) => ({ role: b.role }),
  );
  const remove = useStaffMutation<{ nickname: string }>("DELETE", (b) => `/v1/admin/staff/${encodeURIComponent(b.nickname)}`);
  const error = put.error ?? remove.error;
  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Accessi</div>
          <h1>Staff</h1>
        </div>
      </div>
      <form
        className="card"
        style={{ display: "flex", gap: 12, alignItems: "end", marginBottom: 24 }}
        onSubmit={(e) => {
          e.preventDefault();
          put.mutate({ nickname: nickname.trim().replace(/^@/, ""), role }, { onSuccess: () => setNickname("") });
        }}
      >
        <label className="field" style={{ flex: 1 }}>
          <span>Nickname</span>
          <input className="input" value={nickname} onChange={(e) => setNickname(e.target.value)} required />
        </label>
        <label className="field">
          <span>Ruolo</span>
          <select className="input" value={role} onChange={(e) => setRole(e.target.value as StaffRow["role"])}>
            <option value="moderator">Moderatore</option>
            <option value="admin">Amministratore</option>
          </select>
        </label>
        <button className="btn primary" type="submit" disabled={put.isPending}>
          Aggiungi
        </button>
      </form>
      <p className="muted" style={{ marginTop: -12 }}>
        Chi entra nello staff deve configurare il secondo fattore al primo accesso.
      </p>
      {error ? <p className="error">{errorText(error)}</p> : null}
      <table className="table">
        <thead>
          <tr>
            <th>Persona</th>
            <th>Ruolo</th>
            <th>Dal</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {staff.data?.map((s) => (
            <tr key={s.nickname ?? s.created_at}>
              <td>@{s.nickname ?? "—"}</td>
              <td>{s.role === "admin" ? "Amministratore" : "Moderatore"}</td>
              <td className="muted">{dateTime(s.created_at)}</td>
              <td>
                {s.nickname ? (
                  <button className="btn danger" type="button" onClick={() => remove.mutate({ nickname: s.nickname! })}>
                    Togli
                  </button>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
