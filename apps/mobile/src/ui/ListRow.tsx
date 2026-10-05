import { colors, fonts, spacing } from "@wearx/design-tokens";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { IconChevronRight } from "@/ui/icons";

type Props = {
  label: string;
  description?: string;
  value?: string;
  onPress: () => void;
  tone?: "default" | "danger";
};

/** Riga di un elenco di impostazioni: titolo, descrizione, valore a destra, freccia. */
export function ListRow({ label, description, value, onPress, tone = "default" }: Props) {
  return (
    <Pressable
      role="button"
      onPress={onPress}
      aria-label={[label, value, description].filter(Boolean).join(". ")}
      style={({ pressed }) => [styles.row, pressed && styles.pressed]}
    >
      <View style={styles.text}>
        <Text style={[styles.label, tone === "danger" && styles.danger]}>{label}</Text>
        {description ? <Text style={styles.description}>{description}</Text> : null}
      </View>
      {value ? <Text style={styles.value}>{value}</Text> : null}
      <IconChevronRight color={colors.textTertiary} size={18} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing[3],
    minHeight: 56,
    paddingVertical: spacing[3],
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  pressed: { opacity: 0.7 },
  text: { flex: 1, gap: 3 },
  label: { fontFamily: fonts.uiSemiBold, fontSize: 15, color: colors.text },
  danger: { color: colors.danger },
  description: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 18, color: colors.textSecondary },
  value: { fontFamily: fonts.ui, fontSize: 13, color: colors.textSecondary },
});
