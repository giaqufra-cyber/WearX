import { colors, fonts, minTouchTarget, radii } from "@wearx/design-tokens";
import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

export type ButtonVariant = "primary" | "secondary" | "inverse" | "ghost" | "danger";
export type ButtonSize = "lg" | "md" | "sm";

type Props = {
  label: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: ButtonSize;
  disabled?: boolean;
  /** Mostra un indicatore e blocca la pressione (es. invio in corso). */
  loading?: boolean;
  /** Icona a sinistra del testo. */
  icon?: ReactNode;
  /** Descrive l'effetto per i lettori di schermo, se il testo non basta. */
  hint?: string;
  fullWidth?: boolean;
  testID?: string;
};

const HEIGHTS: Record<ButtonSize, number> = { lg: 56, md: minTouchTarget, sm: 36 };
const FONT_SIZES: Record<ButtonSize, number> = { lg: 16, md: 14, sm: 13 };

/** Pulsante del prototipo: pill, testo in grassetto, quattro varianti di colore. */
export function Button({
  label,
  onPress,
  variant = "primary",
  size = "lg",
  disabled = false,
  loading = false,
  icon,
  hint,
  fullWidth = false,
  testID,
}: Props) {
  const inactive = disabled || loading;
  const palette = PALETTES[variant];
  return (
    <Pressable
      testID={testID}
      role="button"
      aria-label={label}
      aria-disabled={inactive}
      aria-busy={loading}
      accessibilityHint={hint}
      disabled={inactive}
      onPress={onPress}
      // L'area toccabile resta almeno 44 pt anche per i pulsanti piccoli.
      hitSlop={size === "sm" ? 4 : undefined}
      style={({ pressed }) => [
        styles.base,
        { height: HEIGHTS[size], backgroundColor: palette.bg, borderColor: palette.border },
        variant === "ghost" || variant === "danger" ? styles.textOnly : null,
        fullWidth ? styles.fullWidth : null,
        pressed && !inactive ? styles.pressed : null,
        disabled ? styles.disabled : null,
      ]}
    >
      {/* Il testo resta (invisibile) durante il caricamento: il pulsante non cambia larghezza. */}
      <View style={[styles.row, loading ? styles.hidden : null]}>
        {icon}
        <Text style={[styles.label, { color: palette.fg, fontSize: FONT_SIZES[size] }]} numberOfLines={1}>
          {label}
        </Text>
      </View>
      {loading ? <ActivityIndicator color={palette.fg} style={styles.spinner} /> : null}
    </Pressable>
  );
}

const PALETTES: Record<ButtonVariant, { bg: string; fg: string; border: string }> = {
  primary: { bg: colors.accent, fg: colors.onAccent, border: colors.accent },
  secondary: { bg: "transparent", fg: colors.text, border: "#3A3A40" },
  inverse: { bg: colors.inverse, fg: colors.onInverse, border: colors.inverse },
  ghost: { bg: "transparent", fg: colors.text, border: "transparent" },
  danger: { bg: "transparent", fg: colors.danger, border: "transparent" },
};

const styles = StyleSheet.create({
  base: {
    borderRadius: radii.pill,
    borderWidth: 1,
    paddingHorizontal: 20,
    alignItems: "center",
    justifyContent: "center",
    alignSelf: "flex-start",
  },
  textOnly: { paddingHorizontal: 8 },
  fullWidth: { alignSelf: "stretch" },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  hidden: { opacity: 0 },
  spinner: { position: "absolute" },
  label: { fontFamily: fonts.uiExtraBold, letterSpacing: 0.1 },
  pressed: { opacity: 0.85, transform: [{ scale: 0.98 }] },
  disabled: { opacity: 0.35 },
});
