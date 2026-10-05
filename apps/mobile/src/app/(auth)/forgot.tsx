import { colors, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, View } from "react-native";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { authErrorMessage } from "@/features/auth/authErrors";
import { recoveryRedirectUrl } from "@/features/auth/emailLink";
import { NewPasswordFields } from "@/features/auth/NewPasswordFields";
import { saveNewPassword, useRecovery } from "@/features/auth/recovery";
import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";
import { EMAIL_RE } from "@/lib/validation";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";

const CODE_LENGTH = 6;

type Step = "email" | "sent" | "password";

/**
 * Password dimenticata: email -> codice di 6 cifre (o link nella mail) -> nuova password.
 * La risposta è sempre la stessa, che l'email esista o no (niente elenco degli iscritti).
 */
export default function ForgotScreen() {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const recovery = useRecovery();
  const withCode = env.emailOtp;

  const send = async () => {
    if (!EMAIL_RE.test(email.trim()) || busy) return;
    setBusy(true);
    setError(null);
    const { error: failed } = await supabase.auth.resetPasswordForEmail(email.trim().toLowerCase(), {
      redirectTo: recoveryRedirectUrl(),
    });
    setBusy(false);
    // Limite di invii: lo diciamo. Ogni altro esito: stesso messaggio, esista o no l'account.
    if (failed && (failed.status === 429 || String(failed.code).startsWith("over_"))) {
      setError(authErrorMessage(failed));
      return;
    }
    setStep("sent");
  };

  const verify = async (token: string) => {
    if (token.length !== CODE_LENGTH || busy) return;
    setBusy(true);
    setError(null);
    recovery.start();
    const { error: failed } = await supabase.auth.verifyOtp({
      email: email.trim().toLowerCase(),
      token,
      type: "recovery",
    });
    setBusy(false);
    if (failed) {
      recovery.finish();
      setError(authErrorMessage(failed));
      setCode("");
      return;
    }
    setStep("password");
  };

  if (step === "password") {
    return (
      <Screen>
        <AuthHeader />
        <Text variant="display" role="heading">
          Nuova password
        </Text>
        <Text variant="secondary">Scegline una che non usi altrove.</Text>
        <NewPasswordFields
          submitLabel="Salva ed entra"
          onSubmit={async (password) => {
            const failed = await saveNewPassword(password);
            if (failed) return authErrorMessage(failed);
            recovery.finish(); // ora si entra nell'app
            return null;
          }}
        />
      </Screen>
    );
  }

  return (
    <Screen>
      <AuthHeader />
      <Text variant="display" role="heading">
        Password dimenticata
      </Text>
      {step === "email" ? (
        <View style={styles.form}>
          <Text variant="secondary">
            Scrivi l&apos;email del tuo account: ti mandiamo {withCode ? "un codice" : "un link"} per sceglierne una
            nuova.
          </Text>
          <TextField
            label="EMAIL"
            value={email}
            onChangeText={(value) => {
              setEmail(value);
              setError(null);
            }}
            placeholder="nome@esempio.it"
            keyboardType="email-address"
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="email"
            textContentType="emailAddress"
            onSubmitEditing={() => void send()}
            error={error}
          />
          <Button
            label={withCode ? "Mandami il codice" : "Mandami il link"}
            onPress={() => void send()}
            disabled={!EMAIL_RE.test(email.trim())}
            loading={busy}
            fullWidth
          />
        </View>
      ) : (
        <View style={styles.form}>
          <Text variant="secondary">
            Se <Text variant="bodyStrong">{email.trim()}</Text> è registrata, ti è arrivata una mail{" "}
            {withCode
              ? `con un codice di ${CODE_LENGTH} cifre. Scade dopo un'ora.`
              : "con un link: aprilo da questo telefono per scegliere la nuova password. Scade dopo un'ora."}
          </Text>
          {withCode ? (
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
          ) : null}
          <Text variant="secondary" color={colors.textTertiary}>
            Non trovi la mail? Guarda anche nello spam.
          </Text>
          <Button label="Usa un'altra email" variant="ghost" onPress={() => setStep("email")} fullWidth />
        </View>
      )}
      <Button label="Torna all'accesso" variant="ghost" size="md" onPress={() => router.replace("/login")} fullWidth />
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing[4], marginTop: spacing[2] },
});
