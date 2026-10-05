"use client";

import type { BlockedDomain } from "@wearx/api-types";
import { useState } from "react";

import { errorText } from "@/lib/api";
import { dateTime } from "@/lib/format";
import { useStaffMutation, useStaffQuery } from "@/lib/queries";

/**
 * Domini bloccati: phishing, truffe, siti che imitano un marchio. Bloccare un dominio ferma
 * subito tutti i link verso di lui e i suoi sottodomini (anche già pubblicati).
 */
export default function DomainsPage() {
  const domains = useStaffQuery<BlockedDomain[]>("/v1/admin/blocked-domains");
  const [domain, setDomain] = useState("");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState<string | null>(null);
  const add = useStaffMutation<{ domain: string; reason: string }, BlockedDomain>("POST", () => "/v1/admin/blocked-domains");
  const remove = useStaffMutation<{ domain: string }>("DELETE", (b) => `/v1/admin/blocked-domains/${encodeURIComponent(b.domain)}`);
  const error = add.error ?? remove.error;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="mono">Link ai negozi</div>
          <h1>Domini bloccati</h1>
        </div>
      </div>
      <form
        className="card"
        style={{ display: "flex", gap: 12, alignItems: "end", marginBottom: 12 }}
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate({ domain: domain.trim(), reason: reason.trim() }, { onSuccess: () => (setDomain(""), setReason("")) });
        }}
      >
        <label className="field" style={{ flex: 1 }}>
          <span>Dominio</span>
          <input
            className="input"
            value={domain}
            onChange={(e) => setDomain(e.target.value)}
            placeholder="negozio-falso.com"
            required
            minLength={3}
          />
        </label>
        <label className="field" style={{ flex: 2 }}>
          <span>Motivo</span>
          <input
            className="input"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Phishing: imita il sito di un marchio"
            required
            minLength={3}
            maxLength={200}
          />
        </label>
        <button className="btn danger" type="submit" disabled={add.isPending}>
          Blocca
        </button>
      </form>
      <p className="muted" style={{ marginBottom: 20 }}>
        Si blocca anche ogni sottodominio. Chi tocca un link bloccato vede una pagina che spiega perché non lo portiamo
        lì. Ogni blocco finisce nel registro.
      </p>
      {add.data ? (
        <p className="chip ok" role="status" style={{ marginBottom: 16 }}>
          {add.data.domain} bloccato · {add.data.links} {add.data.links === 1 ? "link fermato" : "link fermati"}
        </p>
      ) : null}
      {error ? <p className="error">{errorText(error)}</p> : null}
      {domains.isSuccess && domains.data.length === 0 ? <div className="card empty">Nessun dominio bloccato.</div> : null}
      {domains.data && domains.data.length > 0 ? (
        <table className="table">
          <thead>
            <tr>
              <th>Dominio</th>
              <th>Motivo</th>
              <th>Link</th>
              <th>Dal</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {domains.data.map((d) => (
              <tr key={d.domain}>
                <td>
                  <strong>{d.domain}</strong>
                </td>
                <td>{d.reason}</td>
                <td>{d.links}</td>
                <td className="muted">{dateTime(d.created_at)}</td>
                <td>
                  {confirm === d.domain ? (
                    <button
                      className="btn"
                      type="button"
                      onClick={() => remove.mutate({ domain: d.domain }, { onSuccess: () => setConfirm(null) })}
                    >
                      Conferma sblocco
                    </button>
                  ) : (
                    <button className="btn" type="button" onClick={() => setConfirm(d.domain)}>
                      Sblocca
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
