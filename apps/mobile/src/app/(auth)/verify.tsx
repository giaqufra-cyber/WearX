import { colors, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { authErrorMessage } from "@/features/auth/authErrors";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { supabase } from "@/lib/supabase";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";
import { useToast } from "@/ui/Toast";

const CODE_LENGTH = 6;
const RESEND_COOLDOWN_S = 60;

/** Conferma del contatto con il codice a 6 cifre ricevuto via email o SMS. */
export default function VerifyScreen() {
  const { contact, contactMode } = useSignupDraft();
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
      ? await supabase.auth.resend({ type: "signup", email: contact })
      : await supabase.auth.resend({ type: "sms", phone: contact });
    if (authError) {
      setError(authErrorMessage(authError));
      return;
    }
    setCooldown(RESEND_COOLDOWN_S);
    toast.show("Codice inviato di nuovo.");
  };

  return (
    <Screen>
      <AuthHeader step="PASSO 1 DI 4" />
      <Text variant="display" role="heading">
        Controlla {isEmail ? "la mail" : "i messaggi"}
      </Text>
      <Text variant="secondary">
        Abbiamo mandato un codice di {CODE_LENGTH} cifre a <Text variant="bodyStrong">{contact}</Text>. Scade dopo
        un'ora.
      </Text>

      <View style={styles.form}>
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
        <Button
          label={cooldown > 0 ? `Invia di nuovo tra ${cooldown}s` : "Invia di nuovo il codice"}
          variant="ghost"
          onPress={() => void resend()}
          disabled={cooldown > 0}
          fullWidth
        />
        <Text variant="secondary" style={styles.note} color={colors.textTertiary}>
          Non trovi il codice? Guarda anche nello spam. Se il contatto è già registrato, accedi con la tua password.
        </Text>
        <Button label="Ho già un account" variant="ghost" size="md" onPress={() => router.replace("/login")} fullWidth />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing[4], marginTop: spacing[4] },
  note: { textAlign: "center" },
});
