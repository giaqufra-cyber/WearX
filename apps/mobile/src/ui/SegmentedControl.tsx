import { colors, fonts, radii } from "@wearx/design-tokens";
import { Pressable, StyleSheet, Text, View } from "react-native";

type Option<T extends string> = { value: T; label: string };

type Props<T extends string> = {
  label: string;
  options: ReadonlyArray<Option<T>>;
  value: T;
  onChange: (value: T) => void;
  size?: "sm" | "md";
};

/** Selettore a segmenti (Email/Telefono, Privato/Business). Un solo valore attivo. */
export function SegmentedControl<T extends string>({ label, options, value, onChange, size = "md" }: Props<T>) {
  return (
    <View role="radiogroup" aria-label={label} style={[styles.group, size === "sm" ? styles.groupSm : null]}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <Pressable
            key={option.value}
            role="radio"
            aria-label={option.label}
            aria-checked={active}
            onPress={() => onChange(option.value)}
            style={[styles.segment, size === "sm" ? styles.segmentSm : null, active ? styles.active : null]}
          >
            <Text style={[styles.text, size === "sm" ? styles.textSm : null, active ? styles.activeText : null]}>
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  group: {
    flexDirection: "row",
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    borderRadius: radii.md,
    padding: 3,
  },
  groupSm: { borderRadius: radii.pill, padding: 2, alignSelf: "flex-start" },
  segment: { flex: 1, height: 40, borderRadius: 11, alignItems: "center", justifyContent: "center" },
  segmentSm: { flexGrow: 0, flexShrink: 0, flexBasis: "auto", height: 28, paddingHorizontal: 12, borderRadius: radii.pill },
  active: { backgroundColor: colors.inverse },
  text: { fontFamily: fonts.uiBold, fontSize: 14, color: colors.textSecondary },
  textSm: { fontSize: 12 },
  activeText: { color: colors.onInverse },
});
