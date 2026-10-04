import { colors, fonts, fontSizes, radii, spacing } from "@wearx/design-tokens";
import { Pressable, StyleSheet, TextInput, View } from "react-native";

import { IconClose, IconSearch } from "@/ui/icons";

type Props = {
  value: string;
  onChangeText: (value: string) => void;
  placeholder: string;
  /** Nome per i lettori di schermo (non c'è un'etichetta visibile). */
  label: string;
  maxLength?: number;
};

/** Campo di ricerca del prototipo: lente a sinistra, croce per svuotare. */
export function SearchField({ value, onChangeText, placeholder, label, maxLength = 40 }: Props) {
  return (
    <View style={styles.box}>
      <IconSearch color={colors.textSecondary} size={20} />
      <TextInput
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.textTertiary}
        selectionColor={colors.accent}
        aria-label={label}
        role="searchbox"
        returnKeyType="search"
        autoCapitalize="none"
        autoCorrect={false}
        maxLength={maxLength}
        style={styles.input}
      />
      {value ? (
        <Pressable role="button" aria-label="Svuota la ricerca" onPress={() => onChangeText("")} hitSlop={10}>
          <IconClose color={colors.textSecondary} size={18} />
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    height: 48,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    paddingHorizontal: 14,
  },
  input: {
    flex: 1,
    minWidth: 0,
    height: 46,
    fontFamily: fonts.ui,
    fontSize: fontSizes.bodyLarge,
    color: colors.text,
    paddingVertical: 0,
    outlineWidth: 0,
    marginHorizontal: spacing[0],
  },
});
