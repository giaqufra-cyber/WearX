import { colors, minTouchTarget, radii } from "@wearx/design-tokens";
import type { ReactNode } from "react";
import { Pressable, StyleSheet } from "react-native";

type Props = {
  /** Obbligatorio: un pulsante con solo icona deve avere un nome per i lettori di schermo. */
  label: string;
  onPress: () => void;
  children: ReactNode;
  variant?: "plain" | "filled" | "scrim";
  disabled?: boolean;
  testID?: string;
};

export function IconButton({ label, onPress, children, variant = "plain", disabled = false, testID }: Props) {
  return (
    <Pressable
      testID={testID}
      role="button"
      aria-label={label}
      aria-disabled={disabled}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.base,
        variant === "filled" && styles.filled,
        variant === "scrim" && styles.scrim,
        pressed && styles.pressed,
        disabled && styles.disabled,
      ]}
    >
      {children}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    width: minTouchTarget,
    height: minTouchTarget,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: radii.pill,
  },
  filled: { backgroundColor: colors.inverse },
  scrim: { backgroundColor: "rgba(10,10,11,0.45)" },
  pressed: { opacity: 0.7 },
  disabled: { opacity: 0.3 },
});
