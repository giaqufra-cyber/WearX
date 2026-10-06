import type { InsightMetric, InsightPeriod, InsightPost } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { Image } from "expo-image";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { bestVariant } from "@/features/feed/format";
import { formatChange, formatMetric, shortDate, useInsights } from "@/features/insights/api";
import { InsightChart } from "@/features/insights/InsightChart";
import { EmptyState } from "@/ui/EmptyState";
import { IconButton } from "@/ui/IconButton";
import { IconBack } from "@/ui/icons";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { SegmentedControl } from "@/ui/SegmentedControl";

const PERIODS: { value: `${InsightPeriod}`; label: string }[] = [
  { value: "7", label: "7 giorni" },
  { value: "28", label: "28 giorni" },
  { value: "90", label: "90 giorni" },
];

const MAX_WIDTH = 560;

/** Insight: come vanno i tuoi fit nel periodo scelto, con il confronto col periodo prima. */
export default function InsightsScreen() {
  const [period, setPeriod] = useState<`${InsightPeriod}`>("7");
  const days = Number(period) as InsightPeriod;
  const insights = useInsights(days);
  const [metric, setMetric] = useState<"impressions" | "votes">("impressions");
  const { width: screen } = useWindowDimensions();
  const width = Math.min(screen, MAX_WIDTH) - spacing[4] * 2;

  let body;
  if (insights.isPending) body = <Loading label="Carico gli insight" />;
  else if (insights.isError) body = <ErrorNotice error={insights.error} onRetry={() => void insights.refetch()} />;
  else {
    const data = insights.data;
    const t = data.totals;
    const empty = data.top_posts.length === 0 && t.impressions.value === 0 && t.votes.value === 0;
    const compare = `vs ${days} giorni prima`;
    body = (
      <>
        <Text style={styles.range}>
          {shortDate(data.start)} – {shortDate(data.end)}
          {data.updated_at ? ` · aggiornato ${updatedLabel(data.updated_at)}` : ""}
        </Text>
        {empty ? (
          <EmptyState
            title="Ancora nessun dato"
            body="Quando qualcuno vede, apre o vota i tuoi fit, qui trovi i numeri del giorno dopo."
            action={{ label: "Pubblica un fit", onPress: () => router.push("/new-post") }}
          />
        ) : (
          <>
            <View style={styles.grid}>
              <Tile label="Visualizzazioni" metric={t.impressions} compare={compare} />
              <Tile label="Voti ricevuti" metric={t.votes} compare={compare} />
              <Tile label="Media voti" value={t.average === null ? "—" : t.average.toFixed(1).replace(".", ",")} />
              <Tile label="Aperture" metric={t.opens} compare={compare} />
              <Tile label="Click ai negozi" metric={t.shop_clicks} compare={compare} />
              <Tile label="Visite al profilo" metric={t.profile_views} compare={compare} />
            </View>

            <View style={styles.card}>
              <View style={styles.cardHead}>
                <Text style={styles.cardTitle} role="heading">
                  {data.bucket === "week" ? "Ogni settimana" : "Ogni giorno"}
                </Text>
                <SegmentedControl
                  label="Misura del grafico"
                  size="sm"
                  options={[
                    { value: "impressions", label: "Viste" },
                    { value: "votes", label: "Voti" },
                  ]}
                  value={metric}
                  onChange={setMetric}
                />
              </View>
              <InsightChart
                key={`${days}-${metric}`}
                points={data.series}
                metric={metric}
                bucket={data.bucket}
                width={width - spacing[4] * 2}
              />
            </View>

            {data.top_posts.length > 0 ? (
              <View style={styles.section}>
                <Text style={styles.kicker}>I TUOI FIT PIÙ VISTI</Text>
                {data.top_posts.map((post, i) => (
                  <TopPost key={post.id} post={post} rank={i + 1} />
                ))}
              </View>
            ) : null}
          </>
        )}
        <Text style={styles.note}>
          Per proteggere chi guarda e vota, i numeri da 1 a 4 compaiono come «&lt;5», la media dei voti appare da 5 voti
          in su e non esiste giorno per giorno. Visualizzazioni, aperture e click contano le persone diverse di ogni
          giorno.
        </Text>
      </>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <IconButton label="Indietro" onPress={() => (router.canGoBack() ? router.back() : router.replace("/profile"))}>
          <IconBack color={colors.text} />
        </IconButton>
        <Text style={styles.title} role="heading">
          Insight
        </Text>
        <View style={styles.spacer} />
      </View>
      <ScrollView contentContainerStyle={[styles.content, { maxWidth: MAX_WIDTH }]}>
        <SegmentedControl label="Periodo" options={PERIODS} value={period} onChange={setPeriod} />
        {body}
      </ScrollView>
    </SafeAreaView>
  );
}

function updatedLabel(iso: string): string {
  const at = new Date(iso);
  const today = new Date();
  const time = at.toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit" });
  return at.toDateString() === today.toDateString() ? `oggi alle ${time}` : `il ${shortDate(iso.slice(0, 10))}`;
}

function Tile({ label, metric, value, compare }: { label: string; metric?: InsightMetric; value?: string; compare?: string }) {
  const shown = value ?? formatMetric(metric?.value);
  const delta = metric ? formatChange(metric) : null;
  const up = (metric?.change ?? 0) > 0;
  return (
    <View
      style={styles.tile}
      accessible
      aria-label={`${label}: ${shown === "<5" ? "meno di 5" : shown}${delta ? `, ${delta} ${compare}` : ""}`}
    >
      <Text style={styles.tileLabel}>{label.toUpperCase()}</Text>
      <Text style={styles.tileValue} maxFontSizeMultiplier={1.3}>
        {shown}
      </Text>
      {delta ? (
        <Text style={styles.tileDelta}>
          <Text style={up ? styles.up : styles.down}>{up ? "▲ " : delta === "=" ? "" : "▼ "}</Text>
          {delta} <Text style={styles.compare}>{compare}</Text>
        </Text>
      ) : (
        <Text style={styles.compare}> </Text>
      )}
    </View>
  );
}

function TopPost({ post, rank }: { post: InsightPost; rank: number }) {
  const thumb = post.thumb ? bestVariant(post.thumb.variants, 120) : undefined;
  return (
    <Pressable
      role="button"
      onPress={() => router.push({ pathname: "/post/[id]", params: { id: post.id } })}
      style={({ pressed }) => [styles.post, pressed && styles.pressed]}
      aria-label={`${rank}. ${post.caption ?? "Fit senza didascalia"}, ${post.style}: ${formatMetric(post.impressions)} visualizzazioni, ${formatMetric(post.votes)} voti`}
    >
      <Text style={styles.rank}>{rank}</Text>
      <Image
        source={thumb ? { uri: thumb } : undefined}
        placeholder={post.blurhash ? { blurhash: post.blurhash } : undefined}
        style={styles.thumb}
        contentFit="cover"
        accessibilityLabel=""
        accessible={false}
      />
      <View style={styles.postText}>
        <Text style={styles.postTitle} numberOfLines={1}>
          {post.caption ?? "Fit senza didascalia"}
        </Text>
        <Text style={styles.postStyle}>{post.style}</Text>
      </View>
      <View style={styles.postNumbers}>
        <Figure value={formatMetric(post.impressions)} label="viste" />
        <Figure value={formatMetric(post.votes)} label="voti" />
        <Figure value={post.average === null ? "—" : String(Math.round(post.average))} label="media" />
      </View>
    </Pressable>
  );
}

function Figure({ value, label }: { value: string; label: string }) {
  return (
    <View style={styles.number}>
      <Text style={styles.numberValue}>{value}</Text>
      <Text style={styles.numberLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 4, minHeight: 52 },
  title: { flex: 1, textAlign: "center", fontFamily: fonts.display, fontSize: 20, color: colors.text },
  spacer: { width: 44 },
  content: { padding: spacing[4], gap: spacing[4], paddingBottom: spacing[8], width: "100%", alignSelf: "center" },
  range: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 0.8, color: colors.textTertiary },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing[2] },
  tile: {
    flexBasis: "48%",
    flexGrow: 1,
    padding: spacing[3],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.surface,
    gap: 4,
  },
  tileLabel: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.2, color: colors.textTertiary },
  tileValue: { fontFamily: fonts.numericBold, fontSize: 26, lineHeight: 32, color: colors.text },
  tileDelta: { fontFamily: fonts.uiSemiBold, fontSize: 12, color: colors.text },
  up: { color: colors.accent },
  down: { color: colors.danger },
  compare: { fontFamily: fonts.ui, fontSize: 11, color: colors.textTertiary },
  card: {
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.surface,
    gap: spacing[2],
  },
  cardHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing[2] },
  cardTitle: { flex: 1, fontFamily: fonts.display, fontSize: 18, color: colors.text },
  section: { gap: spacing[1] },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5, color: colors.textTertiary, marginBottom: 4 },
  post: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing[3],
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  pressed: { opacity: 0.7 },
  rank: { width: 16, fontFamily: fonts.numericBold, fontSize: 14, color: colors.textSecondary, textAlign: "center" },
  thumb: { width: 40, height: 50, borderRadius: radii.xs, backgroundColor: colors.surfaceRaised },
  postText: { flex: 1, gap: 2 },
  postTitle: { fontFamily: fonts.uiSemiBold, fontSize: 14, color: colors.text },
  postStyle: { fontFamily: fonts.display, fontSize: 13, color: colors.textSecondary },
  postNumbers: { flexDirection: "row", gap: spacing[3] },
  number: { alignItems: "flex-end", minWidth: 34 },
  numberValue: { fontFamily: fonts.numericBold, fontSize: 14, color: colors.text },
  numberLabel: { fontFamily: fonts.mono, fontSize: 9, letterSpacing: 0.8, color: colors.textTertiary },
  note: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 18, color: colors.textSecondary },
});
