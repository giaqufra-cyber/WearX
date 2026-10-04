import { colors, spacing } from "@wearx/design-tokens";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { ApiError } from "@/lib/api";
import { Text } from "@/ui/Text";

/** Stati di caricamento ed errore comuni a tutte le schermate (sez. 2 della specifica). */
export function Loading({ label }: { label: string }) {
  return (
    <View style={styles.box} accessibilityRole="progressbar" accessibilityLabel={label}>
      <ActivityIndicator color={colors.textSecondary} />
      <Text variant="secondary">{label}</Text>
    </View>
  );
}

export function ErrorNotice({ error }: { error: unknown }) {
  const message =
    error instanceof ApiError && error.code === "app.update_required"
      ? "Aggiorna WearX per continuare."
      : "Non riusciamo a raggiungere WearX. Controlla la connessione e riprova.";
  const ref = error instanceof ApiError && error.requestId ? `Codice: ${error.requestId}` : null;
  return (
    <View style={styles.box} accessibilityRole="alert">
      <Text color={colors.danger}>{message}</Text>
      {ref ? <Text variant="label">{ref}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { paddingVertical: spacing[8], alignItems: "center", gap: spacing[2] },
});
