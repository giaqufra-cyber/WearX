"use client";

import { type FormEvent, useState } from "react";

import { useAuth } from "@/lib/auth";
import { env } from "@/lib/env";

/** Accesso dello staff: password, poi secondo fattore (configurazione al primo accesso). */
export function Login() {
  const auth = useAuth();
  if (auth.status === "loading") {
    return (
      <div className="login">
        <p className="muted">Caricamento…</p>
      </div>
    );
  }
  return (
    <div className="login">
      <div className="card">
        <div>
          <div className="logo" style={{ margin: 0 }}>
            WEAR<b>X</b>
          </div>
          <div className="mono">Pannello dello staff</div>
        </div>
        {auth.status === "signed_out" ? <Password /> : null}
        {auth.status === "verify_mfa" ? <Code /> : null}
        {auth.status === "enroll_mfa" ? <Enroll /> : null}
        {auth.status === "not_staff" ? (
          <>
            <p>Questo account non fa parte dello staff di WearX.</p>
            <button className="btn" type="button" onClick={() => void auth.signOut()}>
              Esci
            </button>
          </>
        ) : null}
        {auth.error ? (
          <p className="error" role="alert">
            {auth.error}
          </p>
        ) : null}
        {env.devLogin && auth.status === "signed_out" ? <DevToken /> : null}
      </div>
    </div>
  );
}

function Password() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    await signIn(email, password);
    setBusy(false);
  };
  return (
    <form onSubmit={submit} style={{ display: "grid", gap: 12 }}>
      <label className="field">
        <span>Email</span>
        <input className="input" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </label>
      <label className="field">
        <span>Password</span>
        <input className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </label>
      <button className="btn primary" type="submit" disabled={busy}>
        Accedi
      </button>
    </form>
  );
}

function Code({ factorId }: { factorId?: string }) {
  const { verify } = useAuth();
  const [code, setCode] = useState("");
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void verify(code, factorId);
      }}
      style={{ display: "grid", gap: 12 }}
    >
      <label className="field">
        <span>Codice dell&apos;app di autenticazione</span>
        <input className="input" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} required />
      </label>
      <button className="btn primary" type="submit">
        Verifica
      </button>
    </form>
  );
}

function Enroll() {
  const { startEnrollment } = useAuth();
  const [enrollment, setEnrollment] = useState<{ factorId: string; qr: string; secret: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  if (!enrollment) {
    return (
      <>
        <p>Lo staff entra solo con il secondo fattore. Configuralo ora con un&apos;app di autenticazione (es. 1Password, Google Authenticator).</p>
        <button
          className="btn primary"
          type="button"
          onClick={() => startEnrollment().then(setEnrollment, (e: Error) => setError(e.message))}
        >
          Configura il secondo fattore
        </button>
        {error ? <p className="error">{error}</p> : null}
      </>
    );
  }
  return (
    <>
      <p>Inquadra il codice con l&apos;app, poi scrivi il codice a 6 cifre.</p>
      <div className="qr">
        {/* eslint-disable-next-line @next/next/no-img-element -- SVG generato da Supabase */}
        <img src={enrollment.qr} alt="Codice QR per l'app di autenticazione" />
      </div>
      <p className="mono" style={{ wordBreak: "break-all" }}>
        {enrollment.secret}
      </p>
      <Code factorId={enrollment.factorId} />
    </>
  );
}

function DevToken() {
  const { signInWithToken } = useAuth();
  const [token, setToken] = useState("");
  return (
    <details>
      <summary className="mono">Sviluppo: accedi con un token</summary>
      <div style={{ display: "grid", gap: 8, marginTop: 8 }}>
        <textarea className="input" aria-label="Token di sviluppo" value={token} onChange={(e) => setToken(e.target.value)} />
        <button className="btn" type="button" onClick={() => void signInWithToken(token)}>
          Usa il token
        </button>
      </div>
    </details>
  );
}
