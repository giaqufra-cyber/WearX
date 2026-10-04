import { colors, radii } from "@wearx/design-tokens";
import { useEffect, useRef, useState } from "react";
import { AccessibilityInfo, Animated, type DimensionValue, StyleSheet } from "react-native";

type Props = { width?: DimensionValue; height: number; radius?: number };

/**
 * Segnaposto durante il caricamento. Pulsa piano; se l'utente ha attivato
 * "riduci movimento" nelle impostazioni del telefono resta fermo.
 */
export function Skeleton({ width = "100%", height, radius = radii.md }: Props) {
  const opacity = useRef(new Animated.Value(0.5)).current;
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    let active = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((enabled) => {
        if (active) setReduceMotion(enabled);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (reduceMotion) return undefined;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.5, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [opacity, reduceMotion]);

  return (
    <Animated.View
      aria-hidden
      style={[styles.base, { width, height, borderRadius: radius, opacity: reduceMotion ? 0.7 : opacity }]}
    />
  );
}

const styles = StyleSheet.create({ base: { backgroundColor: colors.surfaceRaised } });
