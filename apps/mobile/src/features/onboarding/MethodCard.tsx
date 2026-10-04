import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import type { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";

type Props = {
  title: string;
  body: string;
  icon: ReactNode;
  tag?: string;
  onPress: () => void;
  disabled?: boolean;
  loading?: boolean;
};

/** Scheda di un metodo di verifica o di un tipo di profilo (prototipo, passi 2 e 3). */
export function MethodCard({ title, body, icon, tag, onPress, disabled = false, loading = false }: Props) {
  return (
    <Pressable
      role="button"
      aria-label={`${title}. ${body}`}
      aria-disabled={disabled}
      aria-busy={loading}
      disabled={disabled || loading}
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed ? styles.pressed : null, disabled ? styles.disabled : null]}
    >
      <View style={styles.icon}>{loading ? <ActivityIndicator color={colors.accent} /> : icon}</View>
      <View style={styles.text}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.body}>{body}</Text>
      </View>
      {tag ? (
        <View style={styles.tag}>
          <Text style={styles.tagText}>{tag}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

/** Scheda selezionabile (tipo di profilo): bordo d'accento quando scelta. */
export function ChoiceCard({
  title,
  body,
  selected,
  onPress,
  disabled = false,
  note,
}: {
  title: string;
  body: string;
  selected: boolean;
  onPress: () => void;
  disabled?: boolean;
  note?: string;
}) {
  return (
    <Pressable
      role="radio"
      aria-label={note ? `${title}. ${note}` : title}
      aria-checked={selected}
      aria-disabled={disabled}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.choice,
        selected ? styles.choiceOn : null,
        pressed ? styles.pressed : null,
        disabled ? styles.disabled : null,
      ]}
    >
      <View style={styles.choiceHead}>
        <Text style={styles.choiceTitle}>{title}</Text>
        <View style={[styles.radio, selected ? styles.radioOn : null]} />
      </View>
      <Text style={styles.body}>{body}</Text>
      {note ? <Text style={styles.note}>{note}</Text> : null}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    padding: spacing[4],
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  pressed: { opacity: 0.8 },
  disabled: { opacity: 0.4 },
  icon: {
    width: 44,
    height: 44,
    borderRadius: 14,
    backgroundColor: colors.borderSubtle,
    alignItems: "center",
    justifyContent: "center",
  },
  text: { flex: 1 },
  title: { fontFamily: fonts.uiBold, fontSize: 16, color: colors.text },
  body: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 18, color: colors.textSecondary, marginTop: 3 },
  tag: { backgroundColor: colors.accent, borderRadius: 6, paddingHorizontal: 7, paddingVertical: 4 },
  tagText: { fontFamily: fonts.uiExtraBold, fontSize: 10, letterSpacing: 1, color: colors.onAccent },
  choice: {
    padding: 18,
    borderRadius: radii.lg,
    borderWidth: 1.5,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  choiceOn: { borderColor: colors.accent },
  choiceHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  choiceTitle: { fontFamily: fonts.display, fontSize: 24, color: colors.text },
  radio: { width: 22, height: 22, borderRadius: 11, borderWidth: 1.5, borderColor: colors.textTertiary },
  radioOn: { borderWidth: 7, borderColor: colors.accent },
  note: { fontFamily: fonts.uiBold, fontSize: 12, color: colors.warning, marginTop: spacing[2] },
});
