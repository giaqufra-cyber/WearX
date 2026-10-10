import { colors, fonts, spacing } from "@wearx/design-tokens";
import { Pressable, ScrollView, StyleSheet, Text } from "react-native";

import { CATEGORIES, type StyleCategory } from "@/features/styles/catalog";

type Props = {
  value: StyleCategory | null;
  onChange: (value: StyleCategory | null) => void;
  /** Nome del primo filtro (tutti gli stili, dai più seguiti). */
  allLabel?: string;
};

/** Filtro per categoria del catalogo: Più seguiti · Stili · Sport · Accessori · … */
export function CategoryChips({ value, onChange, allLabel = "Più seguiti" }: Props) {
  const options: { key: StyleCategory | null; label: string }[] = [{ key: null, label: allLabel }, ...CATEGORIES];
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      role="tablist"
      aria-label="Categorie di stili"
      contentContainerStyle={styles.row}
      style={styles.bar}
    >
      {options.map((option) => {
        const selected = option.key === value;
        return (
          <Pressable
            key={option.key ?? "all"}
            role="tab"
            aria-selected={selected}
            onPress={() => onChange(option.key)}
            style={[styles.chip, selected && styles.chipOn]}
          >
            <Text style={[styles.text, selected && styles.textOn]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  bar: { flexGrow: 0, marginHorizontal: -spacing[4] },
  row: { gap: spacing[2], paddingHorizontal: spacing[4] },
  chip: {
    height: 36,
    paddingHorizontal: 14,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: "center",
  },
  chipOn: { backgroundColor: colors.text, borderColor: colors.text },
  text: { fontFamily: fonts.uiBold, fontSize: 13, color: colors.textSecondary },
  textOn: { color: colors.background },
});
