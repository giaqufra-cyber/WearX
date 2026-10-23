import { colors, spacing } from "@wearx/design-tokens";
import { ActivityIndicator, StyleSheet, View } from "react-native";

import { ApiError } from "@/lib/api";
import { Button } from "@/ui/Button";
import { Text } from "@/ui/Text";
import { t } from "@/lib/i18n";

/** Stati di caricamento ed errore comuni a tutte le schermate (sez. 2 della specifica). */
export function Loading({ label }: { label: string }) {
  return (
    <View style={styles.box} accessibilityRole="progressbar" accessibilityLabel={label}>
      <ActivityIndicator color={colors.textSecondary} />
      <Text variant="secondary">{label}</Text>
    </View>
  );
}

export function ErrorNotice({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const message =
    error instanceof ApiError && error.code === "app.update_required"
      ? t("Aggiorna WearX per continuare.")
      : t("Non riusciamo a raggiungere WearX. Controlla la connessione e riprova.");
  const ref = error instanceof ApiError && error.requestId ? t("Codice: {requestId}", { requestId: error.requestId }) : null;
  return (
    <View style={styles.box} accessibilityRole="alert">
      <Text color={colors.danger}>{message}</Text>
      {ref ? <Text variant="label">{ref}</Text> : null}
      {onRetry ? <Button label={t("Riprova")} variant="secondary" size="sm" onPress={onRetry} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { paddingVertical: spacing[8], alignItems: "center", gap: spacing[2] },
});
