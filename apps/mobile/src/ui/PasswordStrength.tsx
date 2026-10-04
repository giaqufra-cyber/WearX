import { colors, fonts, fontSizes, spacing } from "@wearx/design-tokens";
import { StyleSheet, Text, View } from "react-native";

import { PASSWORD_LABELS, passwordScore } from "@/lib/validation";

const BAR_COLORS = [colors.dangerStrong, colors.warning, colors.accent, colors.accent] as const;

/** Quattro barre + etichetta, come nel prototipo. Non mostra mai la password. */
export function PasswordStrength({ password }: { password: string }) {
  const score = passwordScore(password);
  const label =
    password === ""
      ? "Almeno 10 caratteri, maiuscole e minuscole, un numero e un simbolo."
      : PASSWORD_LABELS[score];
  const fill = BAR_COLORS[Math.max(0, score - 1)];
  return (
    <View
      style={styles.wrap}
      accessible
      role="progressbar"
      aria-label="Robustezza della password"
      aria-valuemin={0}
      aria-valuemax={4}
      aria-valuenow={score}
      aria-valuetext={label}
    >
      <View style={styles.bars}>
        {[0, 1, 2, 3].map((i) => (
          <View key={i} style={[styles.bar, { backgroundColor: i < score ? fill : "#26262A" }]} />
        ))}
      </View>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 6 },
  bars: { flexDirection: "row", gap: 4, marginTop: spacing[1] },
  bar: { flex: 1, height: 4, borderRadius: 2 },
  label: { fontFamily: fonts.ui, fontSize: fontSizes.label, color: colors.textTertiary },
});
