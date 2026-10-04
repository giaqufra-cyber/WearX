import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { useAppConfig } from "@/features/styles/useAppConfig";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/**
 * Feed degli stili. Seduta 1: intestazione e chip degli stili letti da /v1/config.
 * Il feed vero (card, carosello, voto) arriva nelle sedute 12-13.
 */
export default function FeedScreen() {
  const config = useAppConfig();
  const [filter, setFilter] = useState<string>("all");

  const chips = [{ slug: "all", name: "Tutti" }, ...(config.data?.styles ?? [])];

  return (
    <Screen>
      <View style={styles.header}>
        <Text variant="logo" role="heading" aria-label="WearX">
          WEAR<Text variant="logo" color={colors.accent}>X</Text>
        </Text>
        <Text variant="secondary" style={styles.subtitle}>i tuoi stili</Text>
      </View>

      {config.isPending ? <Loading label="Carico gli stili…" /> : null}
      {config.isError ? <ErrorNotice error={config.error} /> : null}

      {config.data ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          {chips.map((chip) => {
            const active = chip.slug === filter;
            return (
              <Pressable
                key={chip.slug}
                onPress={() => setFilter(chip.slug)}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                style={[styles.chip, active && styles.chipActive]}
              >
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{chip.name}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}

      <View style={styles.notice}>
        <Text variant="label">Qui non si commenta</Text>
        <Text variant="secondary">Si vota da 1 a 100, in forma anonima. Il feed arriva nelle prossime sedute.</Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", paddingTop: spacing[3] },
  subtitle: { fontFamily: fonts.displayRegular, fontSize: 16 },
  chips: { gap: spacing[2], paddingVertical: spacing[1] },
  chip: {
    minHeight: 36,
    paddingHorizontal: 15,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    justifyContent: "center",
  },
  chipActive: { backgroundColor: colors.inverse, borderColor: colors.inverse },
  chipText: { fontFamily: fonts.uiSemiBold, fontSize: 13, color: colors.text },
  chipTextActive: { color: colors.onInverse },
  notice: {
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    borderRadius: radii.lg,
    padding: spacing[4],
    gap: spacing[1],
    marginTop: spacing[3],
  },
});
