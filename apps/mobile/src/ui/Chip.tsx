import { colors, fonts, radii } from "@wearx/design-tokens";
import { Pressable, StyleSheet, Text } from "react-native";

import { toggleState } from "./a11y";

type Props = {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  /** "filter": filtri del feed (Archivo). "style": nomi degli stili (Bodoni). */
  variant?: "filter" | "style";
  /** Colore di sfondo dello stile, per le chip non selezionate di tipo "style". */
  tone?: string;
  testID?: string;
};

export function Chip({ label, selected = false, onPress, variant = "filter", tone, testID }: Props) {
  const interactive = onPress !== undefined;
  return (
    <Pressable
      testID={testID}
      role={interactive ? "button" : "none"}
      aria-label={label}
      {...(interactive ? toggleState(selected) : null)}
      disabled={!interactive}
      onPress={onPress}
      // Chip alte 36 pt: si allarga l'area toccabile fino a 44.
      hitSlop={{ top: 4, bottom: 4 }}
      style={({ pressed }) => [
        styles.base,
        tone && !selected ? { backgroundColor: tone, borderColor: tone } : null,
        selected ? styles.selected : null,
        pressed ? styles.pressed : null,
      ]}
    >
      <Text
        style={[
          variant === "style" ? styles.styleText : styles.filterText,
          selected ? styles.selectedText : null,
        ]}
        numberOfLines={1}
      >
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 36,
    paddingHorizontal: 15,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: "#2E2E33",
    justifyContent: "center",
    alignSelf: "flex-start",
  },
  selected: { backgroundColor: colors.inverse, borderColor: colors.inverse },
  pressed: { opacity: 0.8 },
  filterText: { fontFamily: fonts.uiSemiBold, fontSize: 13, color: colors.text },
  styleText: { fontFamily: fonts.display, fontSize: 15, color: colors.text },
  selectedText: { color: colors.onInverse },
});
