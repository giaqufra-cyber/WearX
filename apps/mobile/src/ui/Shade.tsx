import { useId } from "react";
import { StyleSheet, View, type ViewStyle } from "react-native";
import Svg, { Defs, LinearGradient, Rect, Stop } from "react-native-svg";

type Props = {
  /** "bottom": scuro in basso (per leggere i testi sopra la foto); "top": scuro in alto. */
  from: "bottom" | "top";
  /** Opacità massima, sul lato scuro. */
  max: number;
  color?: string;
  /** Dove sta: top/bottom/height (di base copre tutto il contenitore). */
  style?: ViewStyle;
};

// Punti della curva (morbida all'inizio, piena verso il bordo): una sola sfumatura continua.
const CURVE = [0, 0.1, 0.25, 0.45, 0.7, 1];

/**
 * Sfumatura vera (un gradiente SVG). Prima era fatta di tante strisce di opacità diverse: sul
 * telefono, tra una striscia e l'altra, comparivano righe orizzontali più chiare (seduta 29).
 */
export function Shade({ from, max, color = "#0A0A0B", style }: Props) {
  const id = `shade${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const stops = from === "bottom" ? CURVE : [...CURVE].reverse();
  return (
    <View style={[styles.base, style ?? styles.fill]} pointerEvents="none" aria-hidden>
      <Svg width="100%" height="100%" preserveAspectRatio="none">
        <Defs>
          <LinearGradient id={id} x1="0" y1="0" x2="0" y2="1">
            {stops.map((curve, i) => (
              <Stop
                key={i}
                offset={i / (stops.length - 1)}
                stopColor={color}
                stopOpacity={Math.round(max * curve ** 1.3 * 1000) / 1000}
              />
            ))}
          </LinearGradient>
        </Defs>
        <Rect x="0" y="0" width="100%" height="100%" fill={`url(#${id})`} />
      </Svg>
    </View>
  );
}

const styles = StyleSheet.create({
  base: { position: "absolute", left: 0, right: 0 },
  fill: { top: 0, bottom: 0 },
});
