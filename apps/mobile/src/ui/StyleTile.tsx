import { colors, fonts, radii } from "@wearx/design-tokens";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Badge } from "@/ui/Badge";
import { IconCheck } from "@/ui/icons";

type Props = {
  name: string;
  tagline: string;
  tone: string;
  onPress: () => void;
  /** Modalità scelta (onboarding): mostra il cerchio di selezione. */
  selectable?: boolean;
  selected?: boolean;
  /** Etichetta in alto (es. "Stagionale", "Solo 18+"). */
  badge?: string;
  /** Riga in alto a sinistra (es. numero di membri). */
  meta?: string;
  height?: number;
  testID?: string;
};

/** Riquadro di uno stile: colore dello stile, nome in Bodoni, descrizione breve. */
export function StyleTile({
  name,
  tagline,
  tone,
  onPress,
  selectable = false,
  selected = false,
  badge,
  meta,
  height = 112,
  testID,
}: Props) {
  return (
    <Pressable
      testID={testID}
      role={selectable ? "checkbox" : "button"}
      aria-label={`${name}. ${tagline}`}
      aria-checked={selectable ? selected : undefined}
      onPress={onPress}
      style={({ pressed }) => [
        styles.tile,
        { backgroundColor: tone, height },
        selected ? styles.selected : null,
        pressed ? styles.pressed : null,
      ]}
    >
      <View style={styles.top}>
        {/* Riga, etichetta a sinistra; il cerchio di selezione resta sempre a destra. */}
        <View style={styles.topLeft}>
          {meta ? (
            <Text style={styles.meta} numberOfLines={1}>
              {meta}
            </Text>
          ) : null}
          {badge ? <Badge label={badge} /> : null}
        </View>
        {selectable ? (
          <View style={[styles.dot, selected ? styles.dotOn : null]}>
            {selected ? <IconCheck color={colors.onAccent} size={14} strokeWidth={3} /> : null}
          </View>
        ) : null}
      </View>
      <View>
        <Text style={styles.name} numberOfLines={2}>
          {name}
        </Text>
        <Text style={styles.tagline} numberOfLines={1}>
          {tagline}
        </Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  tile: {
    flex: 1,
    borderRadius: radii.lg,
    padding: 14,
    justifyContent: "space-between",
    borderWidth: 2,
    borderColor: "transparent",
    overflow: "hidden",
  },
  selected: { borderColor: colors.accent },
  pressed: { opacity: 0.88 },
  top: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 6 },
  topLeft: { flex: 1, flexDirection: "row", alignItems: "center", gap: 6, minWidth: 0 },
  meta: { flexShrink: 1, fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1, color: "rgba(242,239,233,0.72)" },
  dot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: "rgba(242,239,233,0.6)",
    alignItems: "center",
    justifyContent: "center",
  },
  dotOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  name: { fontFamily: fonts.display, fontSize: 24, lineHeight: 26, color: colors.text },
  tagline: { fontFamily: fonts.ui, fontSize: 11, marginTop: 5, color: "rgba(242,239,233,0.78)" },
});
