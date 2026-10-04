import { colors, fonts, radii } from "@wearx/design-tokens";
import { StyleSheet, Text } from "react-native";

type Props = { label: string; tone?: "accent" | "inverse" | "outline" };

/** Etichetta piccola in maiuscolo: STAGIONALE, COPERTINA, PRIVATO, ADERITO. */
export function Badge({ label, tone = "accent" }: Props) {
  return (
    <Text style={[styles.base, styles[tone]]}>
      {label.toUpperCase()}
    </Text>
  );
}

const styles = StyleSheet.create({
  base: {
    alignSelf: "flex-start",
    flexShrink: 0,
    fontFamily: fonts.uiExtraBold,
    fontSize: 10,
    letterSpacing: 1.2,
    paddingHorizontal: 7,
    paddingVertical: 4,
    borderRadius: radii.xs,
    overflow: "hidden",
  },
  accent: { backgroundColor: colors.accent, color: colors.onAccent },
  inverse: { backgroundColor: colors.inverse, color: colors.onInverse },
  outline: { borderWidth: 1, borderColor: "#3A3A40", color: colors.textMuted, fontFamily: fonts.mono },
});
