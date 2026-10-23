import type { InfiniteData, UseInfiniteQueryResult } from "@tanstack/react-query";
import type { PortfolioTile, TilePage } from "@wearx/api-types";
import { colors, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { type ReactNode, useMemo } from "react";
import { FlatList, StyleSheet, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { FitTile } from "@/features/portfolio/FitTile";
import { EmptyState } from "@/ui/EmptyState";
import { ErrorNotice } from "@/ui/LoadState";
import { Skeleton } from "@/ui/Skeleton";
import { TopBar } from "@/ui/TopBar";

const MAX_WIDTH = 560;
const SIDE = spacing[4];
const GAP = 8;
const noop = () => undefined;

type Props = {
  title: string;
  query: UseInfiniteQueryResult<InfiniteData<TilePage>>;
  own: boolean;
  empty: { title: string; body: string };
  /** Riga sopra la griglia (spiegazione breve). */
  intro?: ReactNode;
};

/** Griglia a due colonne di fit (Salvati, Archivio), con le pagine che arrivano scorrendo. */
export function TileGrid({ title, query, own, empty, intro }: Props) {
  const { width: screen } = useWindowDimensions();
  const width = Math.floor((Math.min(screen, MAX_WIDTH) - SIDE * 2 - GAP) / 2);
  const tiles = useMemo(() => {
    const seen = new Set<string>();
    return (query.data?.pages ?? []).flatMap((p) => p.items).filter((t) => (seen.has(t.id) ? false : (seen.add(t.id), true)));
  }, [query.data]);
  const open = (tile: PortfolioTile) => router.push({ pathname: "/post/[id]", params: { id: tile.id } });

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title={title} fallback="/profile" />
      <FlatList
        data={tiles}
        keyExtractor={(t) => t.id}
        numColumns={2}
        columnWrapperStyle={styles.row}
        contentContainerStyle={styles.content}
        ListHeaderComponent={intro ? <View style={styles.intro}>{intro}</View> : null}
        onEndReached={() => {
          if (query.hasNextPage && !query.isFetchingNextPage) void query.fetchNextPage();
        }}
        onEndReachedThreshold={0.5}
        renderItem={({ item, index }) => (
          <FitTile
            tile={item}
            index={index}
            width={width}
            isCover={false}
            own={own}
            editing={false}
            canPrev={false}
            canNext={false}
            onOpen={open}
            onPrev={noop}
            onNext={noop}
            numbered={false}
            byline={item.author ? `@${item.author.nickname}` : null}
          />
        )}
        ListEmptyComponent={
          query.isPending ? (
            <View style={styles.row} role="progressbar" aria-label="Carico i fit">
              <Skeleton width={width} height={Math.round(width * 1.28)} />
              <Skeleton width={width} height={Math.round(width * 1.28)} />
            </View>
          ) : query.isError ? (
            <ErrorNotice error={query.error} onRetry={() => void query.refetch()} />
          ) : (
            <EmptyState title={empty.title} body={empty.body} />
          )
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { paddingBottom: spacing[8], maxWidth: MAX_WIDTH, width: "100%", alignSelf: "center" },
  row: { gap: GAP, paddingHorizontal: SIDE, marginBottom: GAP },
  intro: { paddingHorizontal: SIDE, paddingBottom: spacing[3] },
});
