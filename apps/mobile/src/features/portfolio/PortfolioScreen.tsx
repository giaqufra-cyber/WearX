import type { PortfolioTile, UserProfile } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useCallback, useMemo, useState } from "react";
import {
  AccessibilityInfo,
  FlatList,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { initials } from "@/features/feed/format";
import { afterIdForStep, useMoveFit, usePortfolio, useUser } from "@/features/portfolio/api";
import { CapsuleManager } from "@/features/portfolio/CapsuleManager";
import { FitTile } from "@/features/portfolio/FitTile";
import { accountTypeLabel, statValue } from "@/features/portfolio/format";
import { ReportSheet } from "@/features/moderation/ReportSheet";
import { FollowButton } from "@/features/social/FollowButton";
import { PersonMenu } from "@/features/social/PersonMenu";
import { useAppConfig } from "@/features/styles/useAppConfig";
import { ApiError } from "@/lib/api";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { IconButton } from "@/ui/IconButton";
import { IconBack, IconChart, IconFolder, IconLock, IconMore, IconSliders, IconUserPlus } from "@/ui/icons";
import { ErrorNotice } from "@/ui/LoadState";
import { Sheet } from "@/ui/Sheet";
import { Skeleton } from "@/ui/Skeleton";
import { useToast } from "@/ui/Toast";

const MAX_WIDTH = 560;
const GAP = 8;
const SIDE = spacing[4];
const MAX_STYLE_CHIPS = 6;

/** Profilo come portfolio (prototipo, schermata Profilo): statistiche, stili, capsule, griglia. */
export function PortfolioScreen({ nickname }: { nickname: string }) {
  const user = useUser(nickname);
  const profile = user.data;
  const own = profile?.is_self ?? false;
  const [capsule, setCapsule] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [managing, setManaging] = useState(false);
  const [settings, setSettings] = useState(false);
  const [menu, setMenu] = useState(false);
  const [reporting, setReporting] = useState(false);
  const activeCapsule = capsule && profile?.capsules.some((c) => c.id === capsule) ? capsule : null;

  const grid = usePortfolio(nickname, activeCapsule, profile?.can_view_posts ?? false);
  const toast = useToast();
  const move = useMoveFit(nickname, { onError: (message) => toast.show(message, { tone: "error" }) });
  const { width: screen } = useWindowDimensions();
  const contentWidth = Math.min(screen, MAX_WIDTH);
  const tileWidth = Math.floor((contentWidth - SIDE * 2 - GAP) / 2);

  const tiles = useMemo(() => {
    const seen = new Set<string>();
    return (grid.data?.pages ?? []).flatMap((p) => p.items).filter((t) => (seen.has(t.id) ? false : (seen.add(t.id), true)));
  }, [grid.data]);
  const ids = useMemo(() => tiles.map((t) => t.id), [tiles]);
  const coverId = grid.data?.pages[0]?.cover_id ?? null;
  const reordering = editing && own && activeCapsule === null;

  const step = useCallback(
    (tile: PortfolioTile, index: number, direction: -1 | 1) => {
      const afterId = afterIdForStep(ids, index, direction);
      if (afterId === undefined) return;
      move.mutate({ postId: tile.id, afterId });
      const position = index + direction + 1;
      AccessibilityInfo.announceForAccessibility(
        position === 1 ? "Spostato in prima posizione: è la copertina" : `Spostato in posizione ${position}`,
      );
    },
    [ids, move],
  );
  const onPrev = useCallback((tile: PortfolioTile, index: number) => step(tile, index, -1), [step]);
  const onNext = useCallback((tile: PortfolioTile, index: number) => step(tile, index, 1), [step]);
  const onOpen = useCallback(
    (tile: PortfolioTile) => router.push({ pathname: "/post/[id]", params: { id: tile.id } }),
    [],
  );

  const refresh = () => {
    void user.refetch();
    void grid.refetch();
  };

  if (user.isPending) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <View style={styles.skeleton} role="progressbar" aria-label="Carico il profilo">
          <Skeleton height={86} width={86} radius={43} />
          <Skeleton height={20} width={200} />
          <Skeleton height={Math.round(tileWidth * 1.28)} />
        </View>
      </SafeAreaView>
    );
  }
  if (user.isError || !profile) {
    const missing = user.error instanceof ApiError && user.error.status === 404;
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        {missing ? (
          <EmptyState title="Profilo non disponibile" body="Questo profilo non esiste o non è visibile." />
        ) : (
          <ErrorNotice error={user.error} onRetry={() => void user.refetch()} />
        )}
      </SafeAreaView>
    );
  }

  const header = (
    <View>
      <View style={[styles.topBar, !own && styles.topBarBack]}>
        {!own ? (
          <IconButton label="Indietro" onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))}>
            <IconBack color={colors.text} />
          </IconButton>
        ) : null}
        <View style={styles.topName}>
          {profile.account_type === "private" ? <IconLock color={colors.text} size={16} /> : null}
          <Text style={styles.topNick} role="heading" numberOfLines={1}>
            {profile.nickname}
          </Text>
        </View>
        {own ? (
          <>
            <InsightButton />
            <IconButton label="Trova persone" onPress={() => router.push("/find")}>
              <IconUserPlus color={colors.text} />
            </IconButton>
            <IconButton label="Impostazioni dell'account" onPress={() => setSettings(true)}>
              <IconSliders color={colors.text} />
            </IconButton>
          </>
        ) : (
          <IconButton label="Altre azioni" onPress={() => setMenu(true)}>
            <IconMore color={colors.text} />
          </IconButton>
        )}
      </View>

      <ProfileHead profile={profile} />

      {own && (profile.pending_requests ?? 0) > 0 ? (
        <Pressable
          role="button"
          onPress={() => router.push({ pathname: "/people", params: { tab: "requests" } })}
          style={styles.requests}
          aria-label={`Richieste di follow: ${profile.pending_requests}`}
        >
          <Text style={styles.requestsText}>Richieste di follow</Text>
          <Text style={styles.requestsCount}>{profile.pending_requests}</Text>
        </Pressable>
      ) : null}
      {!own ? (
        <View style={styles.buttons}>
          <View style={styles.flex}>
            <FollowButton user={profile} />
          </View>
        </View>
      ) : null}

      {own ? (
        <View style={styles.buttons}>
          <View style={styles.flex}>
            <Button
              label={reordering ? "Fatto" : "Modifica ordine"}
              variant={reordering ? "inverse" : "secondary"}
              size="md"
              fullWidth
              disabled={profile.stats.posts < 2 && !reordering}
              onPress={() => {
                setCapsule(null);
                setEditing((value) => !value);
              }}
            />
          </View>
          <View style={styles.flex}>
            <Button
              label="Capsule"
              variant="secondary"
              size="md"
              fullWidth
              icon={<IconFolder color={colors.text} />}
              onPress={() => setManaging(true)}
            />
          </View>
        </View>
      ) : null}
      {reordering ? (
        <Text style={styles.hint}>Sposta i fit con le frecce. Il primo è la copertina del tuo portfolio.</Text>
      ) : null}

      {profile.can_view_posts && profile.capsules.length > 0 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tabs} style={styles.tabsBar}>
          {[{ id: null, name: "Tutti" }, ...profile.capsules].map((tab) => {
            const selected = tab.id === activeCapsule;
            return (
              <Pressable
                key={tab.id ?? "all"}
                role="tab"
                aria-selected={selected}
                onPress={() => {
                  setCapsule(tab.id);
                  if (tab.id !== null) setEditing(false);
                }}
                style={[styles.tab, selected && styles.tabOn]}
              >
                <Text style={[styles.tabText, selected && styles.tabTextOn]}>{tab.name}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : (
        <View style={styles.tabsBar} />
      )}
    </View>
  );

  let empty = null;
  if (!profile.can_view_posts) {
    empty = (
      <EmptyState
        title="Account privato"
        body={`I fit di @${profile.nickname} li vede solo chi viene approvato.`}
      />
    );
  } else if (grid.isPending) {
    empty = (
      <View style={styles.gridSkeleton} role="progressbar" aria-label="Carico i fit">
        <Skeleton height={Math.round(tileWidth * 1.28)} width={tileWidth} />
        <Skeleton height={Math.round(tileWidth * 1.28)} width={tileWidth} />
      </View>
    );
  } else if (grid.isError) {
    empty = <ErrorNotice error={grid.error} onRetry={() => void grid.refetch()} />;
  } else if (activeCapsule) {
    empty = (
      <EmptyState
        title="Capsula vuota"
        body={own ? "Apri un fit e scegli «Capsula» per aggiungerlo qui." : "Qui non ci sono ancora fit."}
      />
    );
  } else {
    empty = own ? (
      <EmptyState
        title="Il tuo portfolio è vuoto"
        body="Pubblica il primo fit: diventa la copertina del tuo profilo."
        action={{ label: "Pubblica un fit", onPress: () => router.push("/new-post") }}
      />
    ) : (
      <EmptyState title="Ancora nessun fit" />
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <FlatList
        data={profile.can_view_posts ? tiles : []}
        keyExtractor={(tile) => tile.id}
        numColumns={2}
        style={styles.list}
        contentContainerStyle={[styles.content, { width: contentWidth }]}
        columnWrapperStyle={styles.row}
        renderItem={({ item, index }) => (
          <FitTile
            tile={item}
            index={index}
            width={tileWidth}
            isCover={activeCapsule === null && item.id === coverId}
            own={own}
            editing={reordering}
            canPrev={index > 0}
            canNext={index < ids.length - 1}
            onOpen={onOpen}
            onPrev={onPrev}
            onNext={onNext}
          />
        )}
        ListHeaderComponent={header}
        ListEmptyComponent={empty}
        onEndReached={() => {
          if (grid.hasNextPage && !grid.isFetchingNextPage) void grid.fetchNextPage();
        }}
        onEndReachedThreshold={1}
        refreshControl={
          <RefreshControl
            refreshing={(user.isRefetching || grid.isRefetching) && !grid.isFetchingNextPage && !move.isPending}
            onRefresh={refresh}
            tintColor={colors.textSecondary}
          />
        }
      />
      {own ? <CapsuleManager visible={managing} onClose={() => setManaging(false)} /> : null}
      {own ? <AccountSheet visible={settings} onClose={() => setSettings(false)} /> : null}
      {!own ? (
        <PersonMenu
          nickname={profile.nickname}
          visible={menu}
          onClose={() => setMenu(false)}
          onReport={() => setReporting(true)}
        />
      ) : null}
      {!own ? (
        <ReportSheet
          target={{ type: "profile", nickname: profile.nickname }}
          visible={reporting}
          onClose={() => setReporting(false)}
        />
      ) : null}
    </SafeAreaView>
  );
}

/** Solo sul proprio profilo, se gli Insight sono attivi (flag dell'API). */
function InsightButton() {
  const on = useAppConfig().data?.feature_flags?.insights === true;
  if (!on) return null;
  return (
    <IconButton label="Insight" onPress={() => router.push("/insights")}>
      <IconChart color={colors.text} />
    </IconButton>
  );
}

function ProfileHead({ profile }: { profile: UserProfile }) {
  const { stats } = profile;
  return (
    <View>
      <View style={styles.head}>
        <View style={styles.ring} aria-hidden>
          <View style={[styles.avatar, { backgroundColor: profile.styles[0]?.tone ?? "#2F3A2B" }]}>
            <Text style={styles.avatarText}>{initials(profile.nickname)}</Text>
          </View>
        </View>
        <View style={styles.stats}>
          <Stat value={statValue(stats.posts, "count")} label="outfit" />
          <Stat value={statValue(stats.average, "average")} label="voto medio" accent />
          <Stat value={statValue(stats.votes, "count")} label="voti ricevuti" />
        </View>
      </View>
      <View style={styles.info}>
        <View style={styles.nameRow}>
          <Text style={styles.name}>@{profile.nickname}</Text>
          <Text style={styles.type}>{accountTypeLabel(profile.account_type)}</Text>
          {profile.relationship.follows_you && !profile.is_self ? <Text style={styles.type}>TI SEGUE</Text> : null}
        </View>
        <View style={styles.counts}>
          <Count
            value={profile.followers}
            label="follower"
            onPress={profile.is_self ? () => router.push({ pathname: "/people", params: { tab: "followers" } }) : undefined}
          />
          <Text style={styles.countDot}>·</Text>
          <Count
            value={profile.following}
            label="seguiti"
            onPress={profile.is_self ? () => router.push({ pathname: "/people", params: { tab: "following" } }) : undefined}
          />
        </View>
        {profile.bio ? <Text style={styles.bio}>{profile.bio}</Text> : null}
        {profile.styles.length > 0 ? (
          <View style={styles.styleChips} aria-label={`Stili: ${profile.styles.map((s) => s.name).join(", ")}`}>
            {profile.styles.slice(0, MAX_STYLE_CHIPS).map((style) => (
              <Text key={style.slug} style={[styles.styleChip, { backgroundColor: style.tone }]}>
                {style.name}
              </Text>
            ))}
            {profile.styles.length > MAX_STYLE_CHIPS ? (
              <Text style={[styles.styleChip, styles.moreChip]}>+{profile.styles.length - MAX_STYLE_CHIPS}</Text>
            ) : null}
          </View>
        ) : null}
      </View>
    </View>
  );
}

function Count({ value, label, onPress }: { value: number; label: string; onPress?: () => void }) {
  const content = (
    <Text style={styles.countText}>
      <Text style={styles.countValue}>{statValue(value, "count")}</Text> {label}
    </Text>
  );
  return onPress ? (
    <Pressable role="link" onPress={onPress} hitSlop={8} aria-label={`${value} ${label}`}>
      {content}
    </Pressable>
  ) : (
    <View accessible aria-label={`${value} ${label}`}>
      {content}
    </View>
  );
}

function Stat({ value, label, accent = false }: { value: string; label: string; accent?: boolean }) {
  return (
    <View style={styles.stat} accessible aria-label={`${label}: ${value === "—" ? "non disponibile" : value}`}>
      <Text style={[styles.statValue, accent && styles.statAccent]}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function AccountSheet({ visible, onClose }: { visible: boolean; onClose: () => void }) {
  const { signOut } = useAuth();
  return (
    <Sheet visible={visible} title="Account" onClose={onClose}>
      <Button
        label="Notifiche"
        variant="secondary"
        size="md"
        onPress={() => {
          onClose();
          router.push("/notification-settings");
        }}
      />
      <Button
        label="Avvisi della moderazione"
        variant="secondary"
        size="md"
        onPress={() => {
          onClose();
          router.push("/moderation");
        }}
      />
      <Button
        label="Account bloccati"
        variant="secondary"
        size="md"
        onPress={() => {
          onClose();
          router.push({ pathname: "/people", params: { tab: "blocks" } });
        }}
      />
      <Text style={styles.sheetText}>
        Privacy e sicurezza (dispositivi collegati, nascondi prezzi, scarica i tuoi dati) arrivano qui con un
        prossimo aggiornamento.
      </Text>
      <Button
        label="Esci"
        variant="secondary"
        size="md"
        onPress={() => {
          onClose();
          void signOut();
        }}
      />
    </Sheet>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  list: { flex: 1 },
  content: { alignSelf: "center", paddingBottom: spacing[6] },
  row: { gap: GAP, paddingHorizontal: SIDE, marginBottom: GAP },
  flex: { flex: 1 },
  skeleton: { padding: SIDE, gap: spacing[4] },
  gridSkeleton: { flexDirection: "row", gap: GAP, paddingHorizontal: SIDE },
  topBar: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingLeft: SIDE,
    paddingRight: 4,
    minHeight: 52,
  },
  topBarBack: { paddingLeft: 0 },
  requests: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginHorizontal: SIDE,
    marginTop: spacing[4],
    paddingHorizontal: 14,
    minHeight: 48,
    borderRadius: radii.md,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  requestsText: { fontFamily: fonts.uiBold, fontSize: 14, color: colors.text },
  requestsCount: {
    fontFamily: fonts.uiExtraBold,
    fontSize: 12,
    color: colors.onAccent,
    backgroundColor: colors.accent,
    minWidth: 24,
    textAlign: "center",
    paddingHorizontal: 7,
    paddingVertical: 3,
    borderRadius: radii.pill,
    overflow: "hidden",
  },
  counts: { flexDirection: "row", alignItems: "center", gap: 8, marginTop: 6 },
  countText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textSecondary },
  countValue: { fontFamily: fonts.uiBold, color: colors.text },
  countDot: { color: colors.textTertiary },
  topName: { flexDirection: "row", alignItems: "center", gap: 7, flex: 1 },
  topNick: { fontFamily: fonts.uiExtraBold, fontSize: 18, color: colors.text },
  head: { flexDirection: "row", alignItems: "center", gap: 18, paddingHorizontal: SIDE, paddingTop: 6 },
  ring: { width: 86, height: 86, borderRadius: 43, borderWidth: 2, borderColor: colors.accent, padding: 3 },
  avatar: { flex: 1, borderRadius: 40, alignItems: "center", justifyContent: "center" },
  avatarText: { fontFamily: fonts.display, fontSize: 28, color: colors.text },
  stats: { flex: 1, flexDirection: "row" },
  stat: { flex: 1, alignItems: "center" },
  statValue: { fontFamily: fonts.numeric, fontSize: 22, color: colors.text, fontVariant: ["tabular-nums"] },
  statAccent: { color: colors.accent },
  statLabel: { fontFamily: fonts.ui, fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  info: { paddingHorizontal: SIDE, paddingTop: 14 },
  nameRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  name: { fontFamily: fonts.uiBold, fontSize: 15, color: colors.text },
  type: {
    fontFamily: fonts.mono,
    fontSize: 10,
    letterSpacing: 1.2,
    color: colors.textMuted,
    borderWidth: 1,
    borderColor: "#3A3A40",
    borderRadius: radii.xs,
    paddingHorizontal: 6,
    paddingVertical: 3,
  },
  bio: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.textMuted, marginTop: 6 },
  styleChips: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 12 },
  styleChip: {
    fontFamily: fonts.display,
    fontSize: 14,
    color: colors.text,
    paddingHorizontal: 11,
    paddingVertical: 5,
    borderRadius: radii.pill,
    overflow: "hidden",
  },
  moreChip: {
    fontFamily: fonts.uiBold,
    fontSize: 13,
    color: colors.textSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: 6,
  },
  buttons: { flexDirection: "row", gap: GAP, paddingHorizontal: SIDE, paddingTop: spacing[4] },
  hint: {
    fontFamily: fonts.ui,
    fontSize: 12,
    lineHeight: 17,
    color: colors.textSecondary,
    paddingHorizontal: SIDE,
    paddingTop: spacing[3],
  },
  tabsBar: { borderBottomWidth: 1, borderBottomColor: colors.divider, marginTop: 18, marginBottom: 12 },
  tabs: { gap: 22, paddingHorizontal: SIDE },
  tab: { height: 40, justifyContent: "center", borderBottomWidth: 2, borderBottomColor: "transparent" },
  tabOn: { borderBottomColor: colors.accent },
  tabText: { fontFamily: fonts.uiBold, fontSize: 14, color: colors.textSecondary },
  tabTextOn: { color: colors.text },
  sheetText: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.textSecondary },
});
