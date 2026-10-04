import { colors, fonts, fontSizes, spacing } from "@wearx/design-tokens";
import { useEffect, useRef } from "react";
import { Animated, Pressable, StyleSheet, Text, View } from "react-native";

type Props = {
  label: string;
  description?: string;
  value: boolean;
  onValueChange: (next: boolean) => void;
  disabled?: boolean;
  testID?: string;
};

/** Riga impostazione con interruttore (50×30) come nella schermata Privacy del prototipo. */
export function Toggle({ label, description, value, onValueChange, disabled = false, testID }: Props) {
  const knob = useRef(new Animated.Value(value ? 1 : 0)).current;

  useEffect(() => {
    Animated.timing(knob, { toValue: value ? 1 : 0, duration: 160, useNativeDriver: true }).start();
  }, [value, knob]);

  const translateX = knob.interpolate({ inputRange: [0, 1], outputRange: [0, 20] });

  return (
    <Pressable
      testID={testID}
      role="switch"
      aria-label={label}
      aria-checked={value}
      aria-disabled={disabled}
      accessibilityHint={description}
      disabled={disabled}
      onPress={() => onValueChange(!value)}
      style={[styles.row, disabled ? styles.disabled : null]}
    >
      <View style={styles.text}>
        <Text style={styles.label}>{label}</Text>
        {description ? <Text style={styles.description}>{description}</Text> : null}
      </View>
      <View style={[styles.track, { backgroundColor: value ? colors.accent : "#2E2E33" }]}>
        <Animated.View
          style={[
            styles.knob,
            { backgroundColor: value ? colors.onAccent : colors.inverse, transform: [{ translateX }] },
          ]}
        />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing[4],
    paddingVertical: spacing[3],
    minHeight: 56,
  },
  disabled: { opacity: 0.4 },
  text: { flex: 1, gap: 3 },
  label: { fontFamily: fonts.uiSemiBold, fontSize: fontSizes.bodyLarge, color: colors.text },
  description: { fontFamily: fonts.ui, fontSize: fontSizes.label, lineHeight: 17, color: colors.textSecondary },
  track: { width: 50, height: 30, borderRadius: 15, padding: 3, justifyContent: "center" },
  knob: { width: 24, height: 24, borderRadius: 12 },
});
