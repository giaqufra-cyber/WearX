import { spacing } from "@wearx/design-tokens";
import { StyleSheet } from "react-native";

import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Profilo-portfolio. Griglia, riordino e capsule: seduta 14. */
export default function ProfileScreen() {
  return (
    <Screen>
      <Text variant="display" role="heading" style={styles.title}>Il tuo portfolio</Text>
      <Text variant="secondary">I tuoi fit, nell'ordine che scegli tu.</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({ title: { paddingTop: spacing[3] } });
