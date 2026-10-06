import type { Post } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useCallback, useMemo, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  useWindowDimensions,
  View,
  type ViewToken,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useFeed, useVote } from "@/features/feed/api";
import { PostCard } from "@/features/feed/PostCard";
import { NotificationBell } from "@/features/notifications/NotificationBell";
import { useMyStyles } from "@/features/styles/api";
import { track } from "@/lib/events";
import { EmptyState } from "@/ui/EmptyState";
import { IconChat, IconPlus } from "@/ui/icons";
import { ErrorNotice } from "@/ui/LoadState";
import { Skeleton } from "@/ui/Skeleton";
import { Text } from "@/ui/Text";
import { useToast } from "@/ui/Toast";

// Un fit conta come "visto" se resta per almeno un secondo con il 60% sullo schermo.
const VIEWABILITY = { itemVisiblePercentThreshold: 60, minimumViewTime: 1000 };

const MAX_CARD_WIDTH = 560;

/** Feed dei tuoi stili (prototipo, schermata Feed). */
export default function FeedScreen() {
  const mine = useMyStyles();
  const [filter, setFilter] = useState<string>("all");
  const chips = [{ slug: "all", name: "Tutti" }, ...(mine.data?.items ?? [])];
  // Se esci dallo stile selezionato si torna a "Tutti".
  const active = chips.some((c) => c.slug === filter) ? filter : "all";

  const feed = useFeed(active === "all" ? null : active);
  const toast = useToast();
  const vote = useVote({ onError: (message) => toast.show(message, { tone: "error" }) });
  const { width: screen } = useWindowDimensions();
  const width = Math.min(screen, MAX_CARD_WIDTH);

  const posts = useMemo(() => {
    const seen = new Set<string>();
    return (feed.data?.pages ?? []).flatMap((p) => p.items).filter((p) => (seen.has(p.id) ? false : (seen.add(p.id), true)));
  }, [feed.data]);
  const emptyReason = feed.data?.pages[0]?.empty_reason ?? null;

  const onViewable = useRef(({ viewableItems }: { viewableItems: ViewToken<Post>[] }) => {
    for (const token of viewableItems) {
      if (token.isViewable && token.item) track({ name: "post_impression", post_id: token.item.id, source: "feed" });
    }
  }).current;

  const onVote = useCallback(
    (post: Post, score: number, styleConfirm: boolean | null) => vote.mutate({ postId: post.id, score, styleConfirm }),
    [vote],
  );

  const header = (
    <View>
      <View style={styles.header}>
        <Text variant="logo" role="heading" aria-label="WearX" style={styles.logo}>
          WEAR<Text variant="logo" color={colors.accent} style={styles.logo}>X</Text>
        </Text>
        <View style={styles.headerRight}>
          <Text variant="secondary" style={styles.subtitle}>i tuoi stili</Text>
          <NotificationBell />
        </View>
      </View>
      {mine.data ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          <View role="tablist" aria-label="Filtra per stile" style={styles.chipRow}>
          {chips.map((chip) => {
            const selected = chip.slug === active;
            return (
              <Pressable
                key={chip.slug}
                onPress={() => setFilter(chip.slug)}
                role="tab"
                aria-selected={selected}
                style={[styles.chip, selected && styles.chipActive]}
              >
                <Text style={[styles.chipText, selected && styles.chipTextActive]}>{chip.name}</Text>
              </Pressable>
            );
          })}
          </View>
          <Pressable onPress={() => router.navigate("/explore")} role="button" aria-label="Aggiungi stili" style={[styles.chip, styles.chipAdd]}>
            <IconPlus color={colors.textSecondary} size={16} />
            <Text style={[styles.chipText, styles.chipAddText]}>Stili</Text>
          </Pressable>
        </ScrollView>
      ) : null}
      <View style={styles.rule}>
        <IconChat color={colors.textSecondary} size={16} />
        <Text variant="secondary" style={styles.ruleText}>
          Qui non si commenta. Si vota da 1 a 100, in forma anonima.
        </Text>
      </View>
      {mine.isError ? <ErrorNotice error={mine.error} onRetry={() => void mine.refetch()} /> : null}
    </View>
  );

  let empty = null;
  if (feed.isPending) {
    empty = (
      <View style={styles.skeleton} aria-label="Carico il feed" role="progressbar">
        <Skeleton height={38} width={180} radius={19} />
        <Skeleton height={Math.round(width * 1.25)} radius={0} />
        <Skeleton height={44} />
      </View>
    );
  } else if (feed.isError) {
    empty = <ErrorNotice error={feed.error} onRetry={() => void feed.refetch()} />;
  } else if (emptyReason === "no_styles") {
    empty = (
      <EmptyState
        title="Scegli i tuoi stili"
        body="Il feed è fatto dei fit degli stili che segui."
        action={{ label: "Esplora gli stili", onPress: () => router.navigate("/explore") }}
      />
    );
  } else if (posts.length === 0) {
    empty = (
      <EmptyState
        title="Hai visto tutto"
        body="Non ci sono altri fit da votare qui. Sii il primo a postarne uno."
        action={{ label: "Pubblica un fit", onPress: () => router.push("/new-post") }}
      />
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <FlatList
        data={posts}
        keyExtractor={(post) => post.id}
        renderItem={({ item }) => (
          <View style={styles.cardWrap}>
            <PostCard post={item} width={width} onVote={onVote} voting={vote.isPending && vote.variables?.postId === item.id} />
          </View>
        )}
        ListHeaderComponent={header}
        viewabilityConfig={VIEWABILITY}
        onViewableItemsChanged={onViewable}
        ListEmptyComponent={empty}
        ListFooterComponent={
          feed.isFetchingNextPage ? <ActivityIndicator color={colors.textSecondary} style={styles.footer} /> : null
        }
        onEndReached={() => {
          if (feed.hasNextPage && !feed.isFetchingNextPage) void feed.fetchNextPage();
        }}
        onEndReachedThreshold={1.5}
        refreshControl={
          <RefreshControl
            refreshing={feed.isRefetching && !feed.isFetchingNextPage}
            onRefresh={() => void feed.refetch()}
            tintColor={colors.textSecondary}
          />
        }
        windowSize={5}
        initialNumToRender={2}
        maxToRenderPerBatch={3}
        // Mai true: con la nuova architettura di React Native su Android il taglio delle viste
        // fuori schermo fa chiudere l'app ("addViewAt: failed to insert view", trovato da Maestro
        // in seduta 25), soprattutto con il carosello orizzontale dentro la card.
        removeClippedSubviews={false}
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingLeft: spacing[4],
    paddingRight: 4,
    paddingTop: spacing[2],
    paddingBottom: spacing[1],
  },
  headerRight: { flexDirection: "row", alignItems: "center", gap: 2 },
  logo: { fontSize: 26, lineHeight: 30 },
  subtitle: { fontFamily: fonts.displayRegular, fontSize: 16 },
  chips: {
    gap: spacing[2],
    paddingHorizontal: spacing[4],
    paddingTop: 2,
    paddingBottom: spacing[3],
  },
  chipRow: { flexDirection: "row", gap: spacing[2] },
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
  rule: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: spacing[4],
    paddingVertical: spacing[3],
    borderTopWidth: 1,
    borderTopColor: colors.divider,
  },
  ruleText: { flex: 1, fontSize: 12 },
  cardWrap: { alignItems: "center" },
  skeleton: { gap: spacing[3], paddingHorizontal: spacing[4], paddingTop: spacing[2] },
  footer: { paddingVertical: spacing[6] },
});
