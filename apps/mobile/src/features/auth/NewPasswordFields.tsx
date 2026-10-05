import { colors, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { StyleSheet, View } from "react-native";

import { checkPasswordLeak } from "@/features/auth/passwordLeak";
import { PASSWORD_MIN_SCORE, passwordScore } from "@/lib/validation";
import { Button } from "@/ui/Button";
import { PasswordStrength } from "@/ui/PasswordStrength";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";

type Props = {
  submitLabel: string;
  /** Salva la password; restituisce un messaggio d'errore o null se è andata. */
  onSubmit: (password: string) => Promise<string | null>;
  /** Campo in più sopra (es. password attuale). */
  before?: React.ReactNode;
  ready?: boolean;
};

/**
 * Nuova password con le stesse regole della registrazione: robustezza minima, uguale nei due
 * campi, mai una password comparsa in una violazione di dati (controllo k-anonymity).
 */
export function NewPasswordFields({ submitLabel, onSubmit, before, ready = true }: Props) {
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const strong = passwordScore(password) >= PASSWORD_MIN_SCORE;
  const same = password === repeat;
  const canSubmit = ready && strong && same && repeat.length > 0;

  const submit = async () => {
    if (!canSubmit || saving) return;
    setSaving(true);
    setError(null);
    try {
      if ((await checkPasswordLeak(password)) === "compromised") {
        setError("Questa password è comparsa in una violazione di dati online. Scegline un'altra.");
        return;
      }
      setError(await onSubmit(password));
    } finally {
      setSaving(false);
    }
  };

  return (
    <View style={styles.form}>
      {before}
      <TextField
        label="NUOVA PASSWORD"
        value={password}
        onChangeText={(value) => {
          setPassword(value);
          setError(null);
        }}
        secure
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="new-password"
        textContentType="newPassword"
      />
      <PasswordStrength password={password} />
      <TextField
        label="RIPETI LA PASSWORD"
        value={repeat}
        onChangeText={(value) => {
          setRepeat(value);
          setError(null);
        }}
        secure
        autoCapitalize="none"
        autoCorrect={false}
        autoComplete="new-password"
        textContentType="newPassword"
        error={repeat.length > 0 && !same ? "Le due password non coincidono." : null}
        onSubmitEditing={() => void submit()}
      />
      {error ? (
        <Text variant="secondary" color={colors.danger} role="alert">
          {error}
        </Text>
      ) : null}
      <Button label={submitLabel} onPress={() => void submit()} disabled={!canSubmit} loading={saving} fullWidth />
    </View>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing[4] },
});
