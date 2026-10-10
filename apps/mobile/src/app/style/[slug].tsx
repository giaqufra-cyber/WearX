import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import type { PortfolioTile } from "@wearx/api-types";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import { FlatList, Pressable, StyleSheet, Text as RNText, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { FitTile } from "@/features/portfolio/FitTile";
import { type StyleSort, useMembership, useStyle, useStylePosts } from "@/features/styles/api";
import { membersLabel, seasonEndLabel } from "@/features/styles/format";
import { ApiError } from "@/lib/api";
import { EmptyState } from "@/ui/EmptyState";
import { IconBack, IconCheck } from "@/ui/icons";
import { IconButton } from "@/ui/IconButton";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { SegmentedControl } from "@/ui/SegmentedControl";
import { Skeleton } from "@/ui/Skeleton";
import { Text } from "@/ui/Text";
import { useToast } from "@/ui/Toast";

const back = () => (router.canGoBack() ? router.back() : router.replace("/explore"));
const GAP = 8;
const SIDE = spacing[4];
const MAX_WIDTH = 560;
const SORTS: { value: StyleSort; label: string }[] = [
  { value: "top", label: "In evidenza" },
  { value: "new", label: "Recenti" },
];
const noop = () => undefined;

/**
 * Pagina dello stile (prototipo): intestazione colorata, Entra/Esci, regola del match e, dalla
 * seduta 26, la griglia dei fit dello stile (anche i tuoi), in evidenza o dai più recenti.
 */
export default function StylePage() {
  const { slug: raw } = useLocalSearchParams<{ slug: string }>();
  const slug = typeof raw === "string" ? raw : "";
  const style = useStyle(slug);
  const toast = useToast();
  const membership = useMembership({ onError: (message) => toast.show(message, { tone: "error" }) });
  const [sort, setSort] = useState<StyleSort>("top");
  const posts = useStylePosts(style.isSuccess ? slug : "", sort);
  const { width: screen } = useWindowDimensions();
  const contentWidth = Math.min(screen, MAX_WIDTH);
  const tileWidth = Math.floor((contentWidth - SIDE * 2 - GAP) / 2);
  const tiles = useMemo(() => {
    const seen = new Set<string>();
    return (posts.data?.pages ?? []).flatMap((p) => p.items).filter((t) => (seen.has(t.id) ? false : (seen.add(t.id), true)));
  }, [posts.data]);
  const onOpen = useCallback((tile: PortfolioTile) => router.push(`/post/${tile.id}`), []);

  if (style.isPending) {
    return (
      <SafeAreaView style={styles.safe}>
        <TopBar />
        <Loading label="Carico lo stile…" />
      </SafeAreaView>
    );
  }
  if (style.isError) {
    const missing = style.error instanceof ApiError && style.error.status === 404;
    return (
      <SafeAreaView style={styles.safe}>
        <TopBar />
        {missing ? (
          <EmptyState
            title="Stile non disponibile"
            body="Potrebbe essere finita la sua stagione."
            action={{ label: "Torna a Esplora", onPress: () => router.replace("/explore") }}
          />
        ) : (
          <ErrorNotice error={style.error} onRetry={() => void style.refetch()} />
        )}
      </SafeAreaView>
    );
  }

  const data = style.data;
  const joined = data.joined;
  const toggle = () => {
    membership.mutate(
      { slug: data.slug, join: !joined },
      {
        onSuccess: () =>
          toast.show(joined ? `Sei uscito da ${data.name}.` : `Sei entrato in ${data.name}. Lo trovi nel feed.`),
      },
    );
  };

  const header = (
    <View>
      <View style={[styles.hero, { backgroundColor: data.tone }]}>
        <SafeAreaView edges={["top"]} style={styles.heroInner}>
          <RNText style={styles.watermark} aria-hidden numberOfLines={1}>
            {data.name.charAt(0)}
          </RNText>
          <TopBar />
          <View>
            {data.seasonal && data.active_until ? (
              <RNText style={styles.kicker}>STAGIONALE · {seasonEndLabel(data.active_until)}</RNText>
            ) : null}
            <RNText style={styles.kicker}>STILE · {membersLabel(data.member_count).toUpperCase()}</RNText>
            <RNText style={styles.name} role="heading">
              {data.name}
            </RNText>
            <RNText style={styles.tagline}>{data.tagline}</RNText>
            <Pressable
              role="button"
              aria-label={joined ? `Sei dentro ${data.name}. Tocca per uscire` : `Entra in ${data.name}`}
              aria-busy={membership.isPending}
              disabled={membership.isPending}
              onPress={toggle}
              style={({ pressed }) => [
                styles.toggle,
                joined ? styles.toggleJoined : styles.toggleJoin,
                pressed ? styles.pressed : null,
              ]}
            >
              {joined ? <IconCheck color={colors.text} size={16} /> : null}
              <RNText style={[styles.toggleText, joined ? styles.toggleTextJoined : null]}>
                {joined ? "Sei dentro" : "Entra nello stile"}
              </RNText>
            </Pressable>
          </View>
        </SafeAreaView>
      </View>

      <View style={styles.body}>
        <View style={styles.sectionRow}>
          <Text variant="label" style={styles.section}>
            {data.posts_last_7_days === 1 ? "1 FIT QUESTA SETTIMANA" : `${data.posts_last_7_days} FIT QUESTA SETTIMANA`}
          </Text>
        </View>
        <SegmentedControl label="Ordina i fit" options={SORTS} value={sort} onChange={setSort} size="sm" />
      </View>
    </View>
  );

  let empty = null;
  if (posts.isPending) {
    empty = (
      <View style={styles.gridSkeleton} role="progressbar" aria-label="Carico i fit">
        <Skeleton height={Math.round(tileWidth * 1.28)} width={tileWidth} />
        <Skeleton height={Math.round(tileWidth * 1.28)} width={tileWidth} />
      </View>
    );
  } else if (posts.isError) {
    empty = <ErrorNotice error={posts.error} onRetry={() => void posts.refetch()} />;
  } else {
    empty = (
      <EmptyState
        title="Ancora nessun fit in questo stile"
        body={joined ? "Sii il primo a postarne uno." : "Entra nello stile e sii il primo a postarne uno."}
        action={{ label: "Pubblica un fit", onPress: () => router.push("/new-post") }}
      />
    );
  }

  return (
    <View style={styles.root}>
      <FlatList
        data={tiles}
        keyExtractor={(tile) => tile.id}
        numColumns={2}
        style={styles.list}
        contentContainerStyle={[styles.scroll, { width: contentWidth }]}
        columnWrapperStyle={styles.row}
        showsVerticalScrollIndicator={false}
        ListHeaderComponent={header}
        ListEmptyComponent={empty}
        renderItem={({ item, index }) => (
          <FitTile
            tile={item}
            index={index}
            width={tileWidth}
            isCover={false}
            own={item.own}
            editing={false}
            canPrev={false}
            canNext={false}
            numbered={false}
            showStyle={false}
            onOpen={onOpen}
            onPrev={noop}
            onNext={noop}
          />
        )}
        onEndReached={() => {
          if (posts.hasNextPage && !posts.isFetchingNextPage) void posts.fetchNextPage();
        }}
        onEndReachedThreshold={1}
      />
    </View>
  );
}

function TopBar() {
  return (
    <View style={styles.topBar}>
      <IconButton label="Indietro" variant="scrim" onPress={back}>
        <IconBack color={colors.text} size={22} />
      </IconButton>
    </View>
  );
}


const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background, paddingHorizontal: spacing[4] },
  root: { flex: 1, backgroundColor: colors.background },
  list: { flex: 1 },
  scroll: { alignSelf: "center", paddingBottom: spacing[8] },
  row: { gap: GAP, paddingHorizontal: SIDE, marginBottom: GAP },
  gridSkeleton: { flexDirection: "row", gap: GAP, paddingHorizontal: SIDE },
  sectionRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  hero: { minHeight: 300, overflow: "hidden" },
  heroInner: {
    flex: 1,
    minHeight: 300,
    paddingHorizontal: spacing[4],
    paddingBottom: 18,
    justifyContent: "space-between",
  },
  watermark: {
    position: "absolute",
    right: -10,
    top: 30,
    fontFamily: fonts.displayBold,
    fontSize: 190,
    lineHeight: 210,
    color: "rgba(242,239,233,0.06)",
  },
  topBar: { flexDirection: "row", paddingTop: spacing[2], marginLeft: -4 },
  kicker: {
    fontFamily: fonts.mono,
    fontSize: 11,
    letterSpacing: 11 * 0.14,
    color: "rgba(242,239,233,0.75)",
    marginBottom: 4,
  },
  name: { fontFamily: fonts.display, fontSize: 58, lineHeight: 58, color: colors.text, marginTop: 4 },
  tagline: { fontFamily: fonts.ui, fontSize: 14, color: "rgba(242,239,233,0.82)", marginTop: 6 },
  toggle: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    height: 44,
    paddingHorizontal: 22,
    borderRadius: radii.pill,
    borderWidth: 1.5,
    borderColor: colors.text,
    marginTop: spacing[4],
  },
  toggleJoin: { backgroundColor: colors.inverse },
  toggleJoined: { backgroundColor: "transparent" },
  toggleText: { fontFamily: fonts.uiExtraBold, fontSize: 14, color: colors.onInverse },
  toggleTextJoined: { color: colors.text },
  pressed: { opacity: 0.8 },
  body: { paddingHorizontal: spacing[4], gap: spacing[3], marginTop: spacing[4], marginBottom: spacing[4] },
  rule: {
    flexDirection: "row",
    gap: spacing[3],
    alignItems: "flex-start",
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    borderRadius: 16,
    padding: 14,
  },
  ruleText: { flex: 1, fontFamily: fonts.ui, fontSize: 13, lineHeight: 20, color: colors.textMuted },
  ruleStrong: { fontFamily: fonts.uiBold, color: colors.text },
  section: { marginTop: spacing[2] },
});
