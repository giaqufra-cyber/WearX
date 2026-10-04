import { colors, fonts, fontSizes, radii, spacing } from "@wearx/design-tokens";
import { forwardRef, useId, useState } from "react";
import {
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  View,
} from "react-native";

import { IconEye, IconEyeOff } from "@/ui/icons";

type Props = Omit<TextInputProps, "style" | "placeholderTextColor" | "secureTextEntry"> & {
  label: string;
  /** Testo d'aiuto sotto il campo; sostituito dall'errore quando c'è. */
  hint?: string;
  /** Messaggio d'errore: colora il bordo e viene annunciato dai lettori di schermo. */
  error?: string | null;
  /** Testo fisso prima del valore, es. "@" per il nickname. */
  prefix?: string;
  /** Campo password con pulsante mostra/nascondi. */
  secure?: boolean;
  /** Colore del testo d'aiuto (es. accento quando il nickname è libero). */
  hintColor?: string;
  centered?: boolean;
};

/** Campo di testo del prototipo: etichetta mono maiuscola, bordo 1 pt, altezza 52. */
export const TextField = forwardRef<TextInput, Props>(function TextField(
  { label, hint, error, prefix, secure = false, hintColor, centered = false, onFocus, onBlur, ...input },
  ref,
) {
  const id = useId();
  const [focused, setFocused] = useState(false);
  const [revealed, setRevealed] = useState(false);
  const message = error ?? hint;

  return (
    <View style={styles.wrap}>
      <Text nativeID={`${id}-label`} style={styles.label}>
        {label}
      </Text>
      <View
        style={[
          styles.box,
          focused ? styles.boxFocused : null,
          error ? styles.boxError : null,
        ]}
      >
        {prefix ? <Text style={styles.prefix}>{prefix}</Text> : null}
        <TextInput
          ref={ref}
          {...input}
          aria-label={label}
          aria-invalid={Boolean(error)}
          secureTextEntry={secure && !revealed}
          placeholderTextColor={colors.textTertiary}
          selectionColor={colors.accent}
          onFocus={(e) => {
            setFocused(true);
            onFocus?.(e);
          }}
          onBlur={(e) => {
            setFocused(false);
            onBlur?.(e);
          }}
          style={[styles.input, centered ? styles.centered : null]}
        />
        {secure ? (
          <Pressable
            role="button"
            aria-label={revealed ? "Nascondi password" : "Mostra password"}
            onPress={() => setRevealed((v) => !v)}
            style={styles.reveal}
          >
            {revealed ? (
              <IconEyeOff color={colors.textSecondary} />
            ) : (
              <IconEye color={colors.textSecondary} />
            )}
          </Pressable>
        ) : null}
      </View>
      {message ? (
        <Text
          role={error ? "alert" : undefined}
          aria-live={error ? "polite" : undefined}
          style={[styles.message, { color: error ? colors.danger : (hintColor ?? colors.textTertiary) }]}
        >
          {message}
        </Text>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  wrap: { gap: spacing[2] },
  label: {
    fontFamily: fonts.uiBold,
    fontSize: fontSizes.caption,
    letterSpacing: fontSizes.caption * 0.12,
    color: colors.textSecondary,
    textTransform: "uppercase",
  },
  box: {
    minHeight: 52,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: spacing[4],
  },
  boxFocused: { borderColor: colors.textTertiary },
  boxError: { borderColor: colors.dangerStrong },
  prefix: { fontFamily: fonts.ui, fontSize: fontSizes.input, color: colors.textTertiary, marginRight: 2 },
  input: {
    flex: 1,
    // Senza minWidth 0 il campo non si restringe sotto la sua larghezza "naturale" (es. giorno/mese/anno affiancati).
    minWidth: 0,
    minHeight: 50,
    // Il bordo del riquadro indica già il focus: niente contorno del browser sul web.
    outlineWidth: 0,
    fontFamily: fonts.ui,
    fontSize: fontSizes.input,
    color: colors.text,
    paddingVertical: 0,
  },
  centered: { textAlign: "center" },
  reveal: { width: 44, height: 44, alignItems: "center", justifyContent: "center", marginRight: -12 },
  message: { fontFamily: fonts.ui, fontSize: fontSizes.label, lineHeight: 17 },
});

export const labelStyle = styles.label;
