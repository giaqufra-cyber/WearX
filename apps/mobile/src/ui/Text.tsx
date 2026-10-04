import { colors, fonts, fontSizes, letterSpacing } from "@wearx/design-tokens";
import { Text as RNText, type TextProps, StyleSheet } from "react-native";

/**
 * Varianti tipografiche del prototipo. Ogni testo dell'app passa da qui:
 * niente fontFamily o fontSize scritti a mano nelle schermate.
 */
export type TextVariant =
  | "display" // titoli di schermata, Bodoni dritto
  | "headline"
  | "title"
  | "body"
  | "bodyStrong"
  | "secondary"
  | "label" // etichetta mono maiuscola
  | "score" // numeri grandi Archivo largo
  | "logo";

type Props = TextProps & { variant?: TextVariant; color?: string };

export function Text({ variant = "body", color, style, ...rest }: Props) {
  return (
    <RNText
      {...rest}
      maxFontSizeMultiplier={variant === "logo" || variant === "score" ? 1.2 : 2}
      style={[styles[variant], color ? { color } : null, style]}
    />
  );
}

const styles = StyleSheet.create({
  display: {
    fontFamily: fonts.display,
    fontSize: fontSizes.display,
    lineHeight: fontSizes.display * 1.02,
    color: colors.text,
  },
  headline: {
    fontFamily: fonts.display,
    fontSize: fontSizes.headline,
    lineHeight: fontSizes.headline * 1.05,
    color: colors.text,
  },
  title: { fontFamily: fonts.display, fontSize: fontSizes.title, color: colors.text },
  body: {
    fontFamily: fonts.ui,
    fontSize: fontSizes.body,
    lineHeight: fontSizes.body * 1.45,
    color: colors.text,
  },
  bodyStrong: { fontFamily: fonts.uiBold, fontSize: fontSizes.body, color: colors.text },
  secondary: {
    fontFamily: fonts.ui,
    fontSize: fontSizes.body,
    lineHeight: fontSizes.body * 1.5,
    color: colors.textSecondary,
  },
  label: {
    fontFamily: fonts.mono,
    fontSize: fontSizes.caption,
    letterSpacing: fontSizes.caption * letterSpacing.label,
    textTransform: "uppercase",
    color: colors.textSecondary,
  },
  score: {
    fontFamily: fonts.numeric,
    fontSize: fontSizes.score,
    lineHeight: fontSizes.score * 0.95,
    color: colors.accent,
    fontVariant: ["tabular-nums"],
  },
  logo: {
    fontFamily: fonts.numeric,
    fontSize: 26,
    letterSpacing: 26 * letterSpacing.tight,
    color: colors.text,
  },
});
