import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { StyleSheet, View } from "react-native";

import { useAppConfig } from "@/features/styles/useAppConfig";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Esplora. Seduta 1: griglia degli stili dal backend. Ricerca e pagina stile: seduta 7. */
export default function ExploreScreen() {
  const config = useAppConfig();
  return (
    <Screen>
      <Text variant="display" accessibilityRole="header" style={styles.title}>Esplora</Text>
      {config.isPending ? <Loading label="Carico gli stili…" /> : null}
      {config.isError ? <ErrorNotice error={config.error} /> : null}
      <View style={styles.grid}>
        {config.data?.styles.map((style) => (
          <View key={style.slug} style={[styles.card, { backgroundColor: style.tone }]}>
            {style.seasonal ? <Text variant="label" color={colors.onAccent} style={styles.badge}>Stagionale</Text> : <View />}
            <View>
              <Text style={styles.name}>{style.name}</Text>
              <Text style={styles.tagline} numberOfLines={2}>{style.tagline}</Text>
            </View>
          </View>
        ))}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  title: { paddingTop: spacing[3] },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing[2] },
  card: {
    width: "48.5%",
    height: 150,
    borderRadius: radii.lg,
    padding: 14,
    justifyContent: "space-between",
  },
  badge: {
    alignSelf: "flex-start",
    backgroundColor: colors.accent,
    paddingHorizontal: 6,
    paddingVertical: 3,
    borderRadius: radii.xs,
    overflow: "hidden",
  },
  name: { fontFamily: fonts.display, fontSize: 26, lineHeight: 28, color: colors.text },
  tagline: { fontFamily: fonts.ui, fontSize: 11, lineHeight: 15, color: "rgba(242,239,233,0.78)", marginTop: 6 },
});
