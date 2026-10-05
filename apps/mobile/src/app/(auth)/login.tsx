import { colors, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useRef, useState } from "react";
import { StyleSheet, type TextInput, View } from "react-native";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { authErrorMessage } from "@/features/auth/authErrors";
import { type ContactMode, normalizeContact, signInCredentials } from "@/features/auth/credentials";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";
import { EMAIL_RE, PHONE_RE } from "@/lib/validation";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { SegmentedControl } from "@/ui/SegmentedControl";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";

const CONTACT_OPTIONS = [
  { value: "email", label: "Email" },
  { value: "phone", label: "Telefono" },
] as const;

/** Accesso con email (o telefono) e password. */
export default function LoginScreen() {
  const [mode, setMode] = useState<ContactMode>("email");
  const [contact, setContact] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const passwordRef = useRef<TextInput>(null);

  const isEmail = mode === "email";
  const contactOk = isEmail ? EMAIL_RE.test(contact.trim()) : PHONE_RE.test(contact.trim());
  const canSubmit = contactOk && password.length > 0;

  const submit = async () => {
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const { error: authError } = await supabase.auth.signInWithPassword(signInCredentials(mode, contact, password));
      if (!authError) return; // la sessione arriva al layout principale, che cambia schermata
      if (authError.code === "email_not_confirmed" || authError.code === "phone_not_confirmed") {
        // Account creato ma mai confermato: si riprende dal codice.
        useSignupDraft.getState().set({ contactMode: mode, contact: normalizeContact(mode, contact) });
        router.push("/verify");
        return;
      }
      setError(authErrorMessage(authError));
      setPassword("");
    } catch (caught) {
      setError(authErrorMessage(caught as { code?: unknown }));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Screen>
      <AuthHeader />
      <Text variant="display" role="heading">
        Bentornato
      </Text>
      <Text variant="secondary">Accedi per vedere i fit dei tuoi stili.</Text>

      <View style={styles.form}>
        {env.phoneSignupEnabled ? (
          <SegmentedControl
            label="Come vuoi accedere"
            options={CONTACT_OPTIONS}
            value={mode}
            onChange={(next) => {
              setMode(next);
              setContact("");
              setError(null);
            }}
            size="sm"
          />
        ) : null}
        <TextField
          label={isEmail ? "EMAIL" : "TELEFONO"}
          value={contact}
          onChangeText={(value) => {
            setContact(value);
            setError(null);
          }}
          placeholder={isEmail ? "nome@esempio.it" : "+39 333 123 4567"}
          keyboardType={isEmail ? "email-address" : "phone-pad"}
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete={isEmail ? "email" : "tel"}
          textContentType={isEmail ? "emailAddress" : "telephoneNumber"}
          returnKeyType="next"
          onSubmitEditing={() => passwordRef.current?.focus()}
        />
        <TextField
          ref={passwordRef}
          label="PASSWORD"
          value={password}
          onChangeText={(value) => {
            setPassword(value);
            setError(null);
          }}
          secure
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="current-password"
          textContentType="password"
          returnKeyType="go"
          onSubmitEditing={() => void submit()}
        />
        {error ? (
          <Text variant="secondary" color={colors.danger} role="alert">
            {error}
          </Text>
        ) : null}
        <Button label="Accedi" onPress={() => void submit()} disabled={!canSubmit} loading={submitting} fullWidth />
        {isEmail ? (
          <Button label="Password dimenticata?" variant="ghost" size="md" onPress={() => router.push("/forgot")} fullWidth />
        ) : null}
        <Button label="Crea un account" variant="ghost" size="md" onPress={() => router.replace("/signup")} fullWidth />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing[4], marginTop: spacing[4] },
});
