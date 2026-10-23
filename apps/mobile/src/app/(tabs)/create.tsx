import { spacing } from "@wearx/design-tokens";
import { StyleSheet } from "react-native";

import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { t } from "@/lib/i18n";

/** Nuovo fit. Galleria, stile, capi e pubblicazione: seduta 10. */
export default function CreateScreen() {
  return (
    <Screen>
      <Text variant="display" role="heading" style={styles.title}>{t("Nuovo fit")}</Text>
      <Text variant="secondary">{t("Qui sceglierai da 1 a 10 foto, lo stile e i capi indossati.")}</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({ title: { paddingTop: spacing[3] } });
