import { colors, fonts, fontSizes, radii, spacing } from "@wearx/design-tokens";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { IconCheck } from "@/ui/icons";

type Props = {
  label: string;
  checked: boolean;
  onChange: (next: boolean) => void;
  testID?: string;
};

/** Casella con testo (consensi della registrazione). Tutta la riga è toccabile. */
export function Checkbox({ label, checked, onChange, testID }: Props) {
  return (
    <Pressable
      testID={testID}
      role="checkbox"
      aria-label={label}
      aria-checked={checked}
      onPress={() => onChange(!checked)}
      style={styles.row}
    >
      <View style={[styles.box, checked ? styles.boxOn : null]}>
        {checked ? <IconCheck color={colors.onAccent} size={14} strokeWidth={3} /> : null}
      </View>
      <Text style={styles.label}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: spacing[3], alignItems: "flex-start", minHeight: 44, paddingVertical: 2 },
  box: {
    width: 22,
    height: 22,
    borderRadius: radii.xs,
    borderWidth: 1.5,
    borderColor: colors.textTertiary,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 1,
  },
  boxOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  label: { flex: 1, fontFamily: fonts.ui, fontSize: fontSizes.small, lineHeight: 19, color: colors.textMuted },
});
