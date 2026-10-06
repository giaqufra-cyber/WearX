import type { AppNotification } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { Image } from "expo-image";
import { router } from "expo-router";
import { memo, useEffect, useMemo, useRef } from "react";
import { ActivityIndicator, FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";

import { bestVariant } from "@/features/feed/format";
import { timeAgo, useMarkAllRead, useNotifications } from "@/features/notifications/api";
import { PushPrompt } from "@/features/notifications/PushPrompt";
import { safeRoute } from "@/features/notifications/push";
import { usePeopleAction } from "@/features/social/api";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { IconChart, IconShield } from "@/ui/icons";
import { ErrorNotice } from "@/ui/LoadState";
import { Skeleton } from "@/ui/Skeleton";
import { useToast } from "@/ui/Toast";

/**
 * Elenco delle notifiche. Aprendolo, tutte diventano lette; il pallino delle nuove resta visibile
 * finché non si esce, così si capisce cosa è arrivato.
 */
export function NotificationList() {
  const list = useNotifications();
  const markAll = useMarkAllRead();
  const toast = useToast();
  const decide = usePeopleAction("requests", { onError: (message) => toast.show(message, { tone: "error" }) });

  const items = useMemo(() => {
    const seen = new Set<string>();
    return (list.data?.pages ?? []).flatMap((p) => p.items).filter((n) => (seen.has(n.id) ? false : (seen.add(n.id), true)));
  }, [list.data]);

  // Le non lette al momento dell'apertura: restano evidenziate per questa visita.
  const fresh = useRef<Set<string> | null>(null);
  if (fresh.current === null && list.data) {
    fresh.current = new Set(items.filter((n) => !n.read).map((n) => n.id));
  }
  const unread = list.data?.pages[0]?.unread ?? 0;
  const { mutate: markAllRead } = markAll;
  useEffect(() => {
    if (unread > 0) markAllRead();
  }, [unread, markAllRead]);

  let empty = null;
  if (list.isPending) {
    empty = (
      <View style={styles.skeleton} role="progressbar" aria-label="Carico le notifiche">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} height={56} />
        ))}
      </View>
    );
  } else if (list.isError) {
    empty = <ErrorNotice error={list.error} onRetry={() => void list.refetch()} />;
  } else {
    empty = (
      <EmptyState
        title="Nessuna notifica"
        body="Qui trovi chi ti segue, i traguardi dei tuoi fit e gli avvisi della moderazione."
      />
    );
  }

  return (
    <FlatList
      removeClippedSubviews={false} // vedi il feed: su Android chiudeva l'app
      data={items}
      keyExtractor={(n) => n.id}
      renderItem={({ item }) => (
        <NotificationRow
          item={item}
          fresh={fresh.current?.has(item.id) ?? false}
          deciding={decide.isPending && decide.variables?.nickname === item.actor?.nickname}
          onDecide={(accept) => item.actor && decide.mutate({ nickname: item.actor.nickname, accept })}
        />
      )}
      ListHeaderComponent={<PushPrompt />}
      ListEmptyComponent={empty}
      ItemSeparatorComponent={Separator}
      ListFooterComponent={list.isFetchingNextPage ? <ActivityIndicator color={colors.textSecondary} style={styles.footer} /> : null}
      onEndReached={() => {
        if (list.hasNextPage && !list.isFetchingNextPage) void list.fetchNextPage();
      }}
      refreshControl={
        <RefreshControl
          refreshing={list.isRefetching && !list.isFetchingNextPage}
          onRefresh={() => void list.refetch()}
          tintColor={colors.textSecondary}
        />
      }
      contentContainerStyle={styles.content}
    />
  );
}

function Separator() {
  return <View style={styles.separator} />;
}

type RowProps = {
  item: AppNotification;
  fresh: boolean;
  deciding: boolean;
  onDecide: (accept: boolean) => void;
};

const NotificationRow = memo(function NotificationRow({ item, fresh, deciding, onDecide }: RowProps) {
  const isRequest = item.type === "follow_request";
  // Una richiesta porta al profilo di chi la fa (se si può aprire), le altre dove dice l'API.
  const target = safeRoute(isRequest && item.actor?.can_open ? `/user/${item.actor.nickname}` : item.url);
  const open = () => {
    if (target && target !== "/notifications") router.push(target as never);
  };
  const thumb = item.post?.thumb ? bestVariant(item.post.thumb.variants, 120) : undefined;
  const when = timeAgo(item.created_at);

  return (
    <View style={[styles.row, fresh && styles.rowFresh]}>
      {fresh ? <View style={styles.dot} /> : null}
      <Pressable
        onPress={open}
        disabled={!target || target === "/notifications"}
        role="button"
        aria-label={`${fresh ? "Nuova. " : ""}${item.title}. ${item.body} ${when}`}
        style={({ pressed }) => [styles.main, pressed && styles.pressed]}
      >
        <Avatar item={item} />
        <View style={styles.text}>
          <Text style={styles.title}>{item.title}</Text>
          {item.body ? <Text style={styles.body}>{item.body}</Text> : null}
          <Text style={styles.when}>{when.toUpperCase()}</Text>
        </View>
        {item.post ? (
          <Image
            source={thumb ? { uri: thumb } : undefined}
            placeholder={item.post.blurhash ? { blurhash: item.post.blurhash } : undefined}
            style={styles.thumb}
            contentFit="cover"
            accessibilityIgnoresInvertColors
            // Decorativa: il pulsante intorno ha già la descrizione.
            accessibilityLabel=""
            accessible={false}
          />
        ) : null}
      </Pressable>
      {/* Fuori dall'area toccabile della riga: un pulsante dentro un pulsante non funziona. */}
      {isRequest ? (
        <View style={styles.actions}>
          <Button label="Accetta" size="sm" variant="primary" loading={deciding} onPress={() => onDecide(true)} />
          <Button label="Rifiuta" size="sm" variant="secondary" disabled={deciding} onPress={() => onDecide(false)} />
        </View>
      ) : null}
    </View>
  );
});

function Avatar({ item }: { item: AppNotification }) {
  if (item.actor) {
    return (
      <View style={styles.avatar}>
        <Text style={styles.initials}>{item.actor.nickname.slice(0, 2).toUpperCase()}</Text>
      </View>
    );
  }
  if (item.type === "vote_milestone") {
    return (
      <View style={[styles.avatar, styles.avatarAccent]}>
        <IconChart color={colors.onAccent} size={20} />
      </View>
    );
  }
  return (
    <View style={styles.avatar}>
      <IconShield color={colors.text} size={20} />
    </View>
  );
}

const styles = StyleSheet.create({
  content: { paddingBottom: spacing[8], flexGrow: 1 },
  skeleton: { gap: spacing[3], padding: spacing[4] },
  footer: { paddingVertical: spacing[6] },
  separator: { height: 1, backgroundColor: colors.divider },
  row: { paddingVertical: 14, paddingHorizontal: spacing[4] },
  main: { flexDirection: "row", alignItems: "flex-start", gap: spacing[3] },
  rowFresh: { backgroundColor: colors.surface },
  pressed: { opacity: 0.7 },
  dot: {
    position: "absolute",
    left: 6,
    top: 32,
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.accent,
  },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceRaised,
    alignItems: "center",
    justifyContent: "center",
  },
  avatarAccent: { backgroundColor: colors.accent, borderColor: colors.accent },
  initials: { fontFamily: fonts.uiExtraBold, fontSize: 13, color: colors.text, letterSpacing: 0.5 },
  text: { flex: 1, gap: 3 },
  title: { fontFamily: fonts.uiSemiBold, fontSize: 14, lineHeight: 19, color: colors.text },
  body: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 18, color: colors.textSecondary },
  when: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1, color: colors.textTertiary, marginTop: 2 },
  actions: { flexDirection: "row", gap: spacing[2], marginTop: spacing[2], marginLeft: 40 + spacing[3] },
  thumb: { width: 44, height: 55, borderRadius: radii.xs, backgroundColor: colors.surfaceRaised },
});
