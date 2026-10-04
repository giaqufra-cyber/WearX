import { spacing } from "@wearx/design-tokens";
import { StyleSheet } from "react-native";

import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Nuovo fit. Galleria, stile, capi e pubblicazione: seduta 10. */
export default function CreateScreen() {
  return (
    <Screen>
      <Text variant="display" accessibilityRole="header" style={styles.title}>Nuovo fit</Text>
      <Text variant="secondary">Qui sceglierai da 1 a 10 foto, lo stile e i capi indossati.</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({ title: { paddingTop: spacing[3] } });
