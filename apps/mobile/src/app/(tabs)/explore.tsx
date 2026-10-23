import type { StyleCard } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text as RNText, View } from "react-native";

import { PeopleSearch } from "@/features/people/PeopleSearch";
import { useStyles } from "@/features/styles/api";
import { inCategory, type StyleCategory } from "@/features/styles/catalog";
import { CategoryChips } from "@/features/styles/CategoryChips";
import { membersLabel, seasonEndLabel, stylesCountLabel } from "@/features/styles/format";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { Badge } from "@/ui/Badge";
import { EmptyState } from "@/ui/EmptyState";
import { ErrorNotice } from "@/ui/LoadState";
import { Screen } from "@/ui/Screen";
import { SearchField } from "@/ui/SearchField";
import { SegmentedControl } from "@/ui/SegmentedControl";
import { Skeleton } from "@/ui/Skeleton";
import { StyleTile } from "@/ui/StyleTile";
import { Text } from "@/ui/Text";

export const SEARCH_DEBOUNCE_MS = 250;

const openStyle = (slug: string) => router.push({ pathname: "/style/[slug]", params: { slug } });

type Tab = "styles" | "people";
const TABS = [
  { value: "styles", label: "Stili" },
  { value: "people", label: "Persone" },
] as const;

/** Cerca: stili (stagionale in evidenza, tutti gli stili) oppure persone (seduta 31). */
export default function ExploreScreen() {
  const params = useLocalSearchParams<{ tab?: string }>();
  const [tab, setTab] = useState<Tab>(params.tab === "people" ? "people" : "styles");
  return (
    <Screen>
      <Text variant="display" role="heading" style={styles.title}>
        Esplora
      </Text>
      <SegmentedControl label="Cosa cercare" options={TABS} value={tab} onChange={setTab} size="sm" />
      {tab === "styles" ? <StylesPane /> : <PeopleSearch />}
    </Screen>
  );
}

function StylesPane() {
  const [query, setQuery] = useState("");
  const debounced = useDebouncedValue(query.trim(), SEARCH_DEBOUNCE_MS);
  const [category, setCategory] = useState<StyleCategory | null>(null);
  const styles_ = useStyles(debounced);
  // Il server li manda già dai più seguiti (seduta 29); la categoria si filtra qui.
  const items = inCategory(styles_.data?.items ?? [], category);
  const featured = !debounced && !category ? items.find((s) => s.seasonal) : undefined;

  const rows: StyleCard[][] = [];
  for (let i = 0; i < items.length; i += 2) rows.push(items.slice(i, i + 2));

  return (
    <>
      <SearchField
        value={query}
        onChangeText={setQuery}
        label="Cerca uno stile"
        placeholder="Cerca: surf, gioielli, emo, galà…"
      />

      <CategoryChips value={category} onChange={setCategory} />

      {featured ? <FeaturedStyle style={featured} /> : null}

      <View style={styles.sectionHead}>
        <RNText style={styles.section}>{debounced ? "RISULTATI" : category ? "I PIÙ SEGUITI" : "TUTTI, DAI PIÙ SEGUITI"}</RNText>
        {styles_.data ? (
          <RNText style={styles.count} aria-live="polite">
            {stylesCountLabel(items.length)}
          </RNText>
        ) : null}
      </View>

      {styles_.isPending ? (
        <View style={styles.grid} aria-label="Carico gli stili" role="progressbar">
          {[0, 1, 2].map((row) => (
            <View key={row} style={styles.row}>
              <View style={styles.cell}>
                <Skeleton height={150} radius={18} />
              </View>
              <View style={styles.cell}>
                <Skeleton height={150} radius={18} />
              </View>
            </View>
          ))}
        </View>
      ) : null}
      {styles_.isError ? <ErrorNotice error={styles_.error} onRetry={() => void styles_.refetch()} /> : null}
      {styles_.isSuccess && items.length === 0 ? (
        <EmptyState
          title="Nessuno stile trovato"
          body="Non c'è? Proponilo: se lo chiedono in tanti, nasce."
          action={{
            label: `Proponi «${debounced}»`,
            onPress: () => router.push({ pathname: "/style-proposals", params: { name: debounced } }),
          }}
        />
      ) : null}

      <View style={styles.grid}>
        {rows.map((row) => (
          <View key={row.map((s) => s.slug).join("|")} style={styles.row}>
            {row.map((style) => (
              <StyleTile
                key={style.slug}
                name={style.name}
                tagline={style.tagline}
                tone={style.tone}
                height={150}
                taglineLines={2}
                meta={membersLabel(style.member_count).toUpperCase()}
                status={style.joined ? "Aderito" : undefined}
                onPress={() => openStyle(style.slug)}
              />
            ))}
            {row.length === 1 ? <View style={styles.cell} /> : null}
          </View>
        ))}
      </View>

      {styles_.isSuccess && items.length > 0 ? (
        <Pressable
          role="link"
          onPress={() => router.push("/style-proposals")}
          style={({ pressed }) => [styles.propose, pressed ? styles.pressed : null]}
        >
          <RNText style={styles.proposeTitle}>Manca il tuo stile?</RNText>
          <RNText style={styles.proposeText}>Proponilo o chiedi quelli proposti dagli altri →</RNText>
        </Pressable>
      ) : null}
    </>
  );
}

function FeaturedStyle({ style }: { style: StyleCard }) {
  return (
    <Pressable
      role="button"
      aria-label={`${style.name}, stile stagionale. ${membersLabel(style.member_count)}. ${style.tagline}`}
      onPress={() => openStyle(style.slug)}
      style={({ pressed }) => [styles.featured, { backgroundColor: style.tone }, pressed ? styles.pressed : null]}
    >
      <RNText style={styles.watermark} aria-hidden>
        {style.name.charAt(0)}
      </RNText>
      <View style={styles.featuredTop}>
        <Badge label="Stagionale" />
        {style.active_until ? <RNText style={styles.until}>{seasonEndLabel(style.active_until)}</RNText> : null}
      </View>
      <View>
        <RNText style={styles.featuredName}>{style.name}</RNText>
        <RNText style={styles.featuredMeta} numberOfLines={1}>
          {membersLabel(style.member_count)} · {style.tagline}
        </RNText>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  title: { paddingTop: spacing[3] },
  sectionHead: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "baseline",
    marginTop: spacing[2],
  },
  section: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 11 * 0.14, color: colors.textSecondary },
  count: { fontFamily: fonts.ui, fontSize: 12, color: colors.textTertiary },
  grid: { gap: spacing[2] },
  row: { flexDirection: "row", gap: spacing[2] },
  cell: { flex: 1 },
  featured: {
    height: 170,
    borderRadius: 22,
    padding: 18,
    justifyContent: "space-between",
    overflow: "hidden",
    marginTop: spacing[2],
  },
  pressed: { opacity: 0.88 },
  propose: {
    marginTop: spacing[3],
    padding: spacing[4],
    borderRadius: radii.lg,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.border,
    gap: 4,
  },
  proposeTitle: { fontFamily: fonts.display, fontSize: 22, color: colors.text },
  proposeText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textSecondary },
  watermark: {
    position: "absolute",
    right: -6,
    bottom: -40,
    fontFamily: fonts.displayBold,
    fontSize: 170,
    lineHeight: 190,
    color: "rgba(242,239,233,0.07)",
  },
  featuredTop: { flexDirection: "row", alignItems: "center", gap: spacing[2] },
  until: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.1, color: "rgba(242,239,233,0.75)" },
  featuredName: { fontFamily: fonts.display, fontSize: 46, lineHeight: 46, color: colors.text },
  featuredMeta: { fontFamily: fonts.ui, fontSize: 13, color: "rgba(242,239,233,0.8)", marginTop: 6 },
});
