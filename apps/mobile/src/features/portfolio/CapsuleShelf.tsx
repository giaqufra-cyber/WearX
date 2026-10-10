import type { Capsule } from "@wearx/api-types";
import { colors, fonts, spacing } from "@wearx/design-tokens";
import { Image } from "expo-image";
import { PixelRatio, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { bestVariant } from "@/features/feed/format";
import { Shade } from "@/ui/Shade";

/**
 * Capsule come "collezioni" di un portfolio (seduta 28): una copertina per capsula, più grande
 * quante più fit contiene. Quattro misure fisse invece di una scala continua: così le schede
 * restano allineate e la differenza si legge a colpo d'occhio.
 */
export const CAPSULE_SIZES = [
  { min: 0, width: 92 }, // vuota o con un fit
  { min: 2, width: 116 },
  { min: 5, width: 144 },
  { min: 10, width: 176 },
] as const;
const RATIO = 1.25; // 4:5, come le foto dei fit

export function capsuleWidth(postCount: number): number {
  let width: number = CAPSULE_SIZES[0].width;
  for (const size of CAPSULE_SIZES) if (postCount >= size.min) width = size.width;
  return width;
}

/** Altezza della fila: quella della scheda più grande presente (le altre stanno in basso). */
export function shelfHeight(capsules: Pick<Capsule, "post_count">[]): number {
  const widest = Math.max(CAPSULE_SIZES[0].width, ...capsules.map((c) => capsuleWidth(c.post_count)));
  return Math.round(widest * RATIO);
}

type Props = {
  capsules: Capsule[];
  /** Numero di fit di "Tutti". */
  total: number;
  active: string | null;
  onSelect: (id: string | null) => void;
};

export function CapsuleShelf({ capsules, total, active, onSelect }: Props) {
  const height = shelfHeight(capsules);
  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>CAPSULE</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        role="tablist"
        aria-label="Capsule"
        contentContainerStyle={[styles.row, { height }]}
      >
        <Pressable
          role="tab"
          aria-selected={active === null}
          aria-label={`Tutti, ${total} fit`}
          onPress={() => onSelect(null)}
          style={[styles.all, active === null && styles.selected]}
        >
          <Text style={styles.allCount}>{total}</Text>
          <Text style={styles.allText}>Tutti</Text>
        </Pressable>
        {capsules.map((capsule) => {
          const selected = capsule.id === active;
          const width = capsuleWidth(capsule.post_count);
          const url = capsule.cover ? bestVariant(capsule.cover.variants, width * PixelRatio.get()) : undefined;
          return (
            <Pressable
              key={capsule.id}
              role="tab"
              aria-selected={selected}
              aria-label={`${capsule.name}, ${capsule.post_count} fit`}
              onPress={() => onSelect(capsule.id)}
              style={[styles.card, { width, height: Math.round(width * RATIO) }, selected && styles.selected]}
            >
              {url ? (
                <Image
                  source={{ uri: url }}
                  contentFit="cover"
                  transition={120}
                  style={StyleSheet.absoluteFill}
                  accessible={false}
                />
              ) : null}
              <Shade from="bottom" max={0.85} color="#000" style={styles.shade} />
              <View style={styles.caption} pointerEvents="none">
                <Text style={styles.name} numberOfLines={2}>
                  {capsule.name}
                </Text>
                <Text style={styles.count}>{capsule.post_count === 1 ? "1 FIT" : `${capsule.post_count} FIT`}</Text>
              </View>
            </Pressable>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginTop: spacing[5], gap: 10 },
  label: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.4, color: colors.textTertiary, paddingHorizontal: spacing[4] },
  row: { gap: 10, paddingHorizontal: spacing[4], alignItems: "flex-end" },
  all: {
    width: 72,
    height: 92,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceRaised,
    justifyContent: "flex-end",
    padding: 10,
  },
  allCount: { fontFamily: fonts.numeric, fontSize: 22, color: colors.text, fontVariant: ["tabular-nums"] },
  allText: { fontFamily: fonts.uiBold, fontSize: 12, color: colors.textSecondary },
  card: {
    borderRadius: 14,
    overflow: "hidden",
    backgroundColor: colors.surfaceRaised,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    justifyContent: "flex-end",
  },
  selected: { borderColor: colors.accent, borderWidth: 2 },
  shade: { top: "35%", bottom: 0 },
  caption: { padding: 10, gap: 2 },
  name: { fontFamily: fonts.display, fontSize: 16, lineHeight: 19, color: colors.text },
  count: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.2, color: colors.textSecondary },
});
