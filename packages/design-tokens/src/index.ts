/**
 * Design token di WearX, ricavati dal prototipo navigabile (tela Claude Design, v0.1).
 * Unica fonte per colori, caratteri, raggi e spaziature: nessun componente
 * dell'app deve scrivere valori a mano.
 *
 * I colori degli stili (Old Money, Jappo, ...) NON stanno qui: arrivano dal
 * backend (`styles.tone`), perché gli stili sono gestiti dall'admin.
 */

export const colors = {
  background: "#0A0A0B",
  surface: "#141416",
  surfaceRaised: "#18181B",
  border: "#2A2A2E",
  borderSubtle: "#1E1E22",
  divider: "#1A1A1D",
  text: "#F2EFE9",
  textSecondary: "#A3A09A",
  textTertiary: "#8A8781",
  textMuted: "#CFCBC4",
  /** Colore d'accento del brand; personalizzabile in futuro. */
  accent: "#D7FF3A",
  onAccent: "#0A0A0B",
  /** Superficie chiara usata per chip attive, toast, pulsanti secondari pieni. */
  inverse: "#F2EFE9",
  onInverse: "#0A0A0B",
  danger: "#FF9A88",
  dangerStrong: "#FF7A66",
  warning: "#FFB547",
  scrim: "rgba(10,10,11,0.72)",
} as const;

export type ColorToken = keyof typeof colors;

/**
 * Famiglie di caratteri (Google Fonts, caricate con expo-font).
 * - display: titoli e nomi degli stili (Bodoni Moda, sempre dritto, mai corsivo).
 * - ui: interfaccia e testi (Archivo, variabile; larghezza 125% per numeri e logo).
 * - mono: etichette in maiuscolo, contatori, prezzi.
 */
export const fonts = {
  display: "BodoniModa_500Medium",
  displayRegular: "BodoniModa_400Regular",
  displayBold: "BodoniModa_700Bold",
  ui: "Archivo_400Regular",
  uiMedium: "Archivo_500Medium",
  uiSemiBold: "Archivo_600SemiBold",
  uiBold: "Archivo_700Bold",
  uiExtraBold: "Archivo_800ExtraBold",
  /**
   * Archivo larghezza 125%: punteggi, statistiche, logo WEARX.
   * File statici ricavati dal font variabile ufficiale (OFL) in apps/mobile/assets/fonts.
   */
  numeric: "ArchivoExpanded_900",
  numericBold: "ArchivoExpanded_800",
  mono: "JetBrainsMono_400Regular",
  monoSemiBold: "JetBrainsMono_600SemiBold",
} as const;

export type FontToken = keyof typeof fonts;

/** Scala tipografica in punti (pt), come nel prototipo. */
export const fontSizes = {
  caption: 11,
  label: 12,
  small: 13,
  body: 14,
  bodyLarge: 15,
  input: 16,
  title: 22,
  headline: 30,
  display: 42,
  score: 50,
  logo: 84,
} as const;

/** Spaziatura letterale per le etichette mono in maiuscolo (em). */
export const letterSpacing = {
  label: 0.14,
  tight: -0.04,
} as const;

export const radii = {
  xs: 6,
  sm: 10,
  md: 14,
  lg: 18,
  xl: 22,
  pill: 999,
} as const;

/** Spaziature su base 4. */
export const spacing = {
  0: 0,
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  7: 28,
  8: 32,
} as const;

/** Area toccabile minima (WCAG 2.2 / linee guida iOS). */
export const minTouchTarget = 44;

/** Fasce testuali del voto 1–100 (prototipo, schermata Feed). */
export const voteMoods: ReadonlyArray<{ max: number; label: string }> = [
  { max: 20, label: "Non fa per me" },
  { max: 40, label: "Così così" },
  { max: 60, label: "Ci sta" },
  { max: 80, label: "Bel fit" },
  { max: 95, label: "Fit pazzesco" },
  { max: 100, label: "Icona di stile" },
];

export function voteMood(score: number): string {
  if (!Number.isInteger(score) || score < 1 || score > 100) {
    throw new RangeError(`Voto fuori intervallo: ${score}`);
  }
  const mood = voteMoods.find((m) => score <= m.max);
  // voteMoods copre 1..100, quindi mood esiste sempre.
  return mood!.label;
}

export const tokens = { colors, fonts, fontSizes, letterSpacing, radii, spacing, minTouchTarget } as const;
export default tokens;
