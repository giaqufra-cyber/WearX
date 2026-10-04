import { colors, spacing } from "@wearx/design-tokens";
import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";
import { StyleSheet, View } from "react-native";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { authErrorMessage } from "@/features/auth/authErrors";
import { emailRedirectUrl, parseAuthRedirect } from "@/features/auth/emailLink";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { Loading } from "@/ui/LoadState";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";
import { useToast } from "@/ui/Toast";

const CODE_LENGTH = 6;
const RESEND_COOLDOWN_S = 60;

/**
 * Conferma del contatto.
 * - Email: link nella mail (modello predefinito di Supabase) che riapre l'app qui con `?code=`;
 *   con l'SMTP personalizzato si passa al codice a 6 cifre (`EXPO_PUBLIC_EMAIL_OTP=1`).
 * - Telefono: codice a 6 cifre via SMS.
 */
export default function VerifyScreen() {
  const params = useLocalSearchParams();
  const redirect = parseAuthRedirect(params);
  const { contact, contactMode } = useSignupDraft();

  if (redirect?.kind === "code") return <LinkConfirm code={redirect.code} />;
  if (redirect?.kind === "error") return <LinkProblem code={redirect.code} />;
  if (!contact) {
    // Si arriva qui senza contatto solo se l'app è stata chiusa a metà: la bozza è in memoria.
    return (
      <Screen>
        <AuthHeader />
        <EmptyState
          title="Ricominciamo"
          body="Per sicurezza non teniamo i dati della registrazione se chiudi l'app. Accedi o crea di nuovo l'account."
          action={{ label: "Accedi", onPress: () => router.replace("/login") }}
        />
      </Screen>
    );
  }
  const isEmail = contactMode === "email";
  return <Waiting contact={contact} isEmail={isEmail} withCode={!isEmail || env.emailOtp} />;
}

/** In attesa: istruzioni, eventuale campo del codice, reinvio dopo 60 secondi. */
function Waiting({ contact, isEmail, withCode }: { contact: string; isEmail: boolean; withCode: boolean }) {
  const toast = useToast();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_S);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((s) => s - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const verify = async (token: string) => {
    if (token.length !== CODE_LENGTH || verifying) return;
    setVerifying(true);
    setError(null);
    try {
      const { error: authError } = isEmail
        ? await supabase.auth.verifyOtp({ email: contact, token, type: "email" })
        : await supabase.auth.verifyOtp({ phone: contact, token, type: "sms" });
      if (authError) {
        setError(authErrorMessage(authError));
        setCode("");
      }
      // Con il codice giusto arriva la sessione: il layout principale passa da solo al passo successivo.
    } catch (caught) {
      setError(authErrorMessage(caught as { code?: unknown }));
    } finally {
      setVerifying(false);
    }
  };

  const resend = async () => {
    setError(null);
    const { error: authError } = isEmail
      ? await supabase.auth.resend({ type: "signup", email: contact, options: { emailRedirectTo: emailRedirectUrl() } })
      : await supabase.auth.resend({ type: "sms", phone: contact });
    if (authError) {
      setError(authErrorMessage(authError));
      return;
    }
    setCooldown(RESEND_COOLDOWN_S);
    toast.show(withCode ? "Codice inviato di nuovo." : "Link inviato di nuovo.");
  };

  return (
    <Screen>
      <AuthHeader step="PASSO 1 DI 4" />
      <Text variant="display" role="heading">
        Controlla {isEmail ? "la mail" : "i messaggi"}
      </Text>
      {withCode ? (
        <Text variant="secondary">
          Abbiamo mandato un codice di {CODE_LENGTH} cifre a <Text variant="bodyStrong">{contact}</Text>. Scade dopo
          un'ora.
        </Text>
      ) : (
        <Text variant="secondary">
          Abbiamo mandato un link di conferma a <Text variant="bodyStrong">{contact}</Text>. Aprilo da questo
          telefono: torni qui e prosegui. Scade dopo un'ora.
        </Text>
      )}

      <View style={styles.form}>
        {withCode ? (
          <>
            <TextField
              label="CODICE"
              value={code}
              onChangeText={(raw) => {
                const next = raw.replace(/\D/g, "").slice(0, CODE_LENGTH);
                setCode(next);
                setError(null);
                if (next.length === CODE_LENGTH) void verify(next);
              }}
              placeholder="000000"
              keyboardType="number-pad"
              maxLength={CODE_LENGTH}
              autoComplete="one-time-code"
              textContentType="oneTimeCode"
              autoFocus
              centered
              error={error}
            />
            <Button
              label="Conferma"
              onPress={() => void verify(code)}
              disabled={code.length !== CODE_LENGTH}
              loading={verifying}
              fullWidth
            />
          </>
        ) : error ? (
          <Text variant="secondary" color={colors.danger} role="alert">
            {error}
          </Text>
        ) : null}
        <Button
          label={cooldown > 0 ? `Invia di nuovo tra ${cooldown}s` : `Invia di nuovo il ${withCode ? "codice" : "link"}`}
          variant={withCode ? "ghost" : "secondary"}
          onPress={() => void resend()}
          disabled={cooldown > 0}
          fullWidth
        />
        <Text variant="secondary" style={styles.note} color={colors.textTertiary}>
          Non trovi {isEmail ? "la mail" : "il messaggio"}? Guarda anche nello spam. Se il contatto è già registrato,
          accedi con la tua password.
        </Text>
        <Button label="Ho già un account" variant="ghost" size="md" onPress={() => router.replace("/login")} fullWidth />
      </View>
    </Screen>
  );
}

/** Aperto dal link nella mail: si scambia il codice monouso con la sessione. */
function LinkConfirm({ code }: { code: string }) {
  const [failed, setFailed] = useState(false);
  const started = useRef<string | null>(null);

  useEffect(() => {
    if (started.current === code) return; // una sola volta per codice, anche in StrictMode
    started.current = code;
    supabase.auth
      .exchangeCodeForSession(code)
      .then(({ error }) => {
        // Riuscito: arriva la sessione e il layout principale passa da solo al passo successivo.
        if (error) setFailed(true);
      })
      .catch(() => setFailed(true));
  }, [code]);

  if (!failed) {
    return (
      <Screen>
        <Loading label="Confermiamo il tuo account…" />
      </Screen>
    );
  }
  // Supabase conferma l'email già al clic: se lo scambio fallisce (link aperto da un altro
  // dispositivo, app reinstallata) basta accedere con la password.
  return (
    <Screen>
      <AuthHeader />
      <EmptyState
        title="Email confermata"
        body="Ora accedi con la tua email e la password che hai scelto."
        action={{ label: "Accedi", onPress: () => router.replace("/login") }}
      />
    </Screen>
  );
}

function LinkProblem({ code }: { code: string }) {
  const expired = code === "otp_expired" || code === "access_denied";
  return (
    <Screen>
      <AuthHeader />
      <EmptyState
        title={expired ? "Link scaduto" : "Link non valido"}
        body={
          expired
            ? "Il link è scaduto o è già stato usato. Accedi: se l'email non è ancora confermata potrai chiederne uno nuovo."
            : "Questo link non funziona. Accedi o crea di nuovo l'account."
        }
        action={{ label: "Accedi", onPress: () => router.replace("/login") }}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing[4], marginTop: spacing[4] },
  note: { textAlign: "center" },
});
