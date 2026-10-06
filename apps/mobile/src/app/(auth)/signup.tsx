import { colors, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useMemo, useRef, useState } from "react";
import { StyleSheet, type TextInput, View } from "react-native";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { BirthDateFields } from "@/features/auth/BirthDateFields";
import { authErrorMessage } from "@/features/auth/authErrors";
import { normalizeContact, signUpCredentials } from "@/features/auth/credentials";
import { emailRedirectUrl } from "@/features/auth/emailLink";
import { checkPasswordLeak } from "@/features/auth/passwordLeak";
import { checkSignup, emptySignup, type SignupForm } from "@/features/auth/signupForm";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { type NicknameAvailability, useNicknameAvailability } from "@/features/auth/useNicknameAvailability";
import { LegalLinkRow } from "@/features/legal/legal";
import { env } from "@/lib/env";
import { supabase } from "@/lib/supabase";
import { Button } from "@/ui/Button";
import { Checkbox } from "@/ui/Checkbox";
import { PasswordStrength } from "@/ui/PasswordStrength";
import { Screen } from "@/ui/Screen";
import { SegmentedControl } from "@/ui/SegmentedControl";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";

const CONTACT_OPTIONS = [
  { value: "email", label: "Email" },
  { value: "phone", label: "Telefono" },
] as const;

const NICK_HINTS: Record<NicknameAvailability, { text: string; color?: string }> = {
  idle: { text: "Minuscole, numeri, punto e underscore." },
  checking: { text: "Controllo…" },
  available: { text: "Libero. È tuo se lo vuoi.", color: colors.accent },
  taken: { text: "Già preso. Prova una variante.", color: colors.danger },
  reserved: { text: "Questo nickname non è disponibile.", color: colors.danger },
  unknown: { text: "Non riusciamo a controllarlo ora: lo verifichiamo alla fine." },
};

/** Registrazione, passo 1 di 4 (prototipo, schermata "Crea account"). */
export default function SignupScreen() {
  const [form, setForm] = useState<SignupForm>(emptySignup);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [leakError, setLeakError] = useState<string | null>(null);
  const contactRef = useRef<TextInput>(null);
  const passwordRef = useRef<TextInput>(null);

  const check = useMemo(() => checkSignup(form, new Date()), [form]);
  const availability = useNicknameAvailability(form.nickname);
  const nickBlocked = availability === "taken" || availability === "reserved";
  const nickHint = NICK_HINTS[availability];

  const update = (patch: Partial<SignupForm>) => {
    setForm((prev) => ({ ...prev, ...patch }));
    setFormError(null);
    if ("password" in patch) setLeakError(null);
  };

  const submit = async () => {
    if (!check.canSubmit || nickBlocked || submitting) return;
    setSubmitting(true);
    setFormError(null);
    try {
      if ((await checkPasswordLeak(form.password)) === "compromised") {
        setLeakError("Questa password è comparsa in una violazione di dati online. Scegline un'altra.");
        return;
      }
      const { data, error } = await supabase.auth.signUp(
        signUpCredentials(form.contactMode, form.contact, form.password, form.nickname, emailRedirectUrl()),
      );
      if (error) {
        setFormError(authErrorMessage(error));
        return;
      }
      // La data di nascita resta solo in memoria: serve al passo della verifica dell'età.
      useSignupDraft.getState().set({
        nickname: form.nickname.trim().toLowerCase(),
        contactMode: form.contactMode,
        contact: normalizeContact(form.contactMode, form.contact),
        birth: { day: Number(form.day), month: Number(form.month), year: Number(form.year) },
      });
      // Con la conferma attiva non c'è sessione finché non si inserisce il codice.
      if (!data.session) router.push("/verify");
    } catch (error) {
      setFormError(authErrorMessage(error as { code?: unknown }));
    } finally {
      setSubmitting(false);
    }
  };

  const isEmail = form.contactMode === "email";

  return (
    <Screen>
      <AuthHeader step="PASSO 1 DI 4" />
      <Text variant="display" role="heading">
        Crea account
      </Text>
      <Text variant="secondary" style={styles.lead}>
        Nickname pubblico, dati di contatto privati. Nessuno vede la tua mail o il tuo numero.
      </Text>

      <View style={styles.fields}>
        <TextField
          label="NICKNAME"
          prefix="@"
          value={form.nickname}
          onChangeText={(nickname) => update({ nickname: nickname.toLowerCase() })}
          placeholder="il.tuo.nick"
          autoCapitalize="none"
          autoCorrect={false}
          autoComplete="username-new"
          textContentType="username"
          maxLength={20}
          returnKeyType="next"
          onSubmitEditing={() => contactRef.current?.focus()}
          error={check.errors.nickname ?? (nickBlocked ? nickHint.text : null)}
          hint={nickHint.text}
          hintColor={nickHint.color}
        />

        <View style={styles.group}>
          {env.phoneSignupEnabled ? (
            <SegmentedControl
              label="Come vuoi registrarti"
              options={CONTACT_OPTIONS}
              value={form.contactMode}
              onChange={(contactMode) => update({ contactMode, contact: "" })}
              size="sm"
            />
          ) : null}
          <TextField
            ref={contactRef}
            label={isEmail ? "EMAIL" : "TELEFONO"}
            value={form.contact}
            onChangeText={(contact) => update({ contact })}
            placeholder={isEmail ? "nome@esempio.it" : "+39 333 123 4567"}
            keyboardType={isEmail ? "email-address" : "phone-pad"}
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete={isEmail ? "email" : "tel"}
            textContentType={isEmail ? "emailAddress" : "telephoneNumber"}
            returnKeyType="next"
            onSubmitEditing={() => passwordRef.current?.focus()}
            error={check.errors.contact}
            hint="Ti mandiamo un codice di conferma. Serve anche per recuperare l'account."
          />
        </View>

        <View style={styles.group}>
          <TextField
            ref={passwordRef}
            label="PASSWORD"
            value={form.password}
            onChangeText={(password) => update({ password })}
            secure
            autoCapitalize="none"
            autoCorrect={false}
            autoComplete="new-password"
            textContentType="newPassword"
            error={leakError ?? check.errors.password}
          />
          <PasswordStrength password={form.password} />
        </View>

        <View style={styles.group}>
          <BirthDateFields value={form} onChange={update} />
          <BirthNote underage={check.underage} ok={check.age !== null && !check.underage && !check.errors.birth} error={check.errors.birth} />
        </View>

        <View style={styles.consents}>
          <Checkbox
            label="Ho letto l'Informativa privacy (GDPR) e accetto i Termini di WearX."
            checked={form.acceptTerms}
            onChange={(acceptTerms) => update({ acceptTerms })}
          />
          <Checkbox
            label="Accetto le regole della community: si vota, non si insulta."
            checked={form.acceptRules}
            onChange={(acceptRules) => update({ acceptRules })}
          />
          <LegalLinkRow docs={["privacy", "terms", "community_rules"]} />
        </View>

        {formError ? (
          <Text variant="secondary" color={colors.danger} role="alert">
            {formError}
          </Text>
        ) : null}

        <Button
          label="Continua"
          onPress={() => void submit()}
          disabled={!check.canSubmit || nickBlocked}
          loading={submitting}
          fullWidth
        />
      </View>
    </Screen>
  );
}

function BirthNote({ underage, ok, error }: { underage: boolean; ok: boolean; error?: string }) {
  if (error) {
    return (
      <Text variant="secondary" color={colors.danger} role="alert">
        {error}
      </Text>
    );
  }
  if (underage) {
    return (
      <Text variant="secondary" color={colors.danger} role="alert">
        WearX è riservata a chi ha almeno 16 anni. Non salviamo i dati che hai inserito.
      </Text>
    );
  }
  if (ok) {
    return (
      <Text variant="secondary" color={colors.accent}>
        Età compatibile. La confermiamo al prossimo passo.
      </Text>
    );
  }
  return <Text variant="secondary">Serve per confermare che hai almeno 16 anni. Non è pubblica.</Text>;
}

const styles = StyleSheet.create({
  lead: { marginBottom: spacing[3] },
  fields: { gap: spacing[5] },
  group: { gap: spacing[2] },
  consents: { gap: spacing[1] },
});
