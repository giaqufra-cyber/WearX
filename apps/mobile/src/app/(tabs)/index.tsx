import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { useMyStyles } from "@/features/styles/api";
import { IconPlus } from "@/ui/icons";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/**
 * Feed degli stili: intestazione e chip dei TUOI stili (GET /v1/me/styles).
 * Il feed vero (card, carosello, voto) arriva nelle sedute 12-13.
 */
export default function FeedScreen() {
  const mine = useMyStyles();
  const [filter, setFilter] = useState<string>("all");

  const chips = [{ slug: "all", name: "Tutti" }, ...(mine.data?.items ?? [])];
  // Se esci dallo stile selezionato si torna a "Tutti".
  const active = chips.some((c) => c.slug === filter) ? filter : "all";

  return (
    <Screen>
      <View style={styles.header}>
        <Text variant="logo" role="heading" aria-label="WearX">
          WEAR<Text variant="logo" color={colors.accent}>X</Text>
        </Text>
        <Text variant="secondary" style={styles.subtitle}>i tuoi stili</Text>
      </View>

      {mine.isPending ? <Loading label="Carico i tuoi stili…" /> : null}
      {mine.isError ? <ErrorNotice error={mine.error} onRetry={() => void mine.refetch()} /> : null}

      {mine.data ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          {chips.map((chip) => {
            const selected = chip.slug === active;
            return (
              <Pressable
                key={chip.slug}
                onPress={() => setFilter(chip.slug)}
                role="button"
                aria-selected={selected}
                style={[styles.chip, selected && styles.chipActive]}
              >
                <Text style={[styles.chipText, selected && styles.chipTextActive]}>{chip.name}</Text>
              </Pressable>
            );
          })}
          <Pressable
            onPress={() => router.navigate("/explore")}
            role="button"
            aria-label="Aggiungi stili"
            style={[styles.chip, styles.chipAdd]}
          >
            <IconPlus color={colors.textSecondary} size={16} />
            <Text style={[styles.chipText, styles.chipAddText]}>Stili</Text>
          </Pressable>
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
  chipAdd: { flexDirection: "row", alignItems: "center", gap: 4, borderStyle: "dashed" },
  chipAddText: { color: colors.textSecondary },
  notice: {
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    borderRadius: radii.lg,
    padding: spacing[4],
    gap: spacing[1],
    marginTop: spacing[3],
  },
});
