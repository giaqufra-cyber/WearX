import { colors, fonts, spacing } from "@wearx/design-tokens";
import { StyleSheet, Text, View } from "react-native";

import { Button } from "@/ui/Button";

type Props = {
  title: string;
  body?: string;
  action?: { label: string; onPress: () => void };
};

/** Stato vuoto (feed senza fit, ricerca senza risultati). Mai una schermata bianca. */
export function EmptyState({ title, body, action }: Props) {
  return (
    <View style={styles.wrap}>
      <Text role="heading" aria-level={2} style={styles.title}>
        {title}
      </Text>
      {body ? <Text style={styles.body}>{body}</Text> : null}
      {action ? (
        // Il pulsante si allinea a sinistra di suo: il contenitore lo riporta al centro.
        <View style={styles.action}>
          <Button label={action.label} onPress={action.onPress} variant="secondary" size="md" />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  action: { alignItems: "center", marginTop: spacing[1] },
  wrap: { alignItems: "center", paddingVertical: spacing[8] * 1.5, paddingHorizontal: spacing[6], gap: spacing[3] },
  title: { fontFamily: fonts.display, fontSize: 24, color: colors.text, textAlign: "center" },
  body: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 21, color: colors.textSecondary, textAlign: "center" },
});
