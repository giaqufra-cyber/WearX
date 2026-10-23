import type { PersonSummary } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { router, useLocalSearchParams } from "expo-router";
import { useMemo, useState } from "react";
import { FlatList, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { type PeopleKind, usePeople, usePeopleAction } from "@/features/social/api";
import { Avatar } from "@/ui/Avatar";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { IconButton } from "@/ui/IconButton";
import { IconBack, IconClose } from "@/ui/icons";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { useToast } from "@/ui/Toast";
import { N_, t } from "@/lib/i18n";

const TABS: ReadonlyArray<{ kind: PeopleKind; label: string }> = [
  { kind: "requests", label: N_("Richieste") },
  { kind: "followers", label: N_("Follower") },
  { kind: "following", label: N_("Seguiti") },
  { kind: "blocks", label: N_("Bloccati") },
];

const EMPTY: Record<PeopleKind, { title: string; body: string }> = {
  requests: { title: N_("Nessuna richiesta"), body: N_("Chi vuole vedere il tuo portfolio compare qui: decidi tu.") },
  followers: { title: N_("Ancora nessun follower"), body: N_("Il tuo account è privato: ti segue solo chi accetti.") },
  following: { title: N_("Non segui nessuno"), body: N_("Cerca un amico per nickname da «Trova persone».") },
  blocks: { title: N_("Nessun account bloccato"), body: N_("Chi blocchi non ti vede e tu non vedi lui.") },
};

const isKind = (value: unknown): value is PeopleKind => TABS.some((t) => t.kind === value);

/** Richieste di follow, follower, seguiti, account bloccati. */
export default function PeopleScreen() {
  const params = useLocalSearchParams<{ tab?: string }>();
  const [tab, setTab] = useState<PeopleKind>(isKind(params.tab) ? params.tab : "requests");
  const back = () => (router.canGoBack() ? router.back() : router.replace("/profile"));

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <IconButton label={t("Indietro")} onPress={back}>
          <IconBack color={colors.text} />
        </IconButton>
        <Text style={styles.title} role="heading">
          {t("Persone")}
        </Text>
        <View style={styles.spacer} />
      </View>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} role="tablist" style={styles.tabsBar} contentContainerStyle={styles.tabs}>
        {TABS.map((entry) => (
          <Pressable
            key={entry.kind}
            role="tab"
            aria-selected={entry.kind === tab}
            onPress={() => setTab(entry.kind)}
            style={[styles.tab, entry.kind === tab && styles.tabOn]}
          >
            <Text style={[styles.tabText, entry.kind === tab && styles.tabTextOn]}>{t(entry.label)}</Text>
          </Pressable>
        ))}
      </ScrollView>
      <PeopleList key={tab} kind={tab} />
    </SafeAreaView>
  );
}

function PeopleList({ kind }: { kind: PeopleKind }) {
  const list = usePeople(kind);
  const toast = useToast();
  const action = usePeopleAction(kind, { onError: (message) => toast.show(message, { tone: "error" }) });
  const people = useMemo(() => (list.data?.pages ?? []).flatMap((p) => p.items), [list.data]);

  if (list.isPending) return <Loading label={t("Carico l'elenco")} />;
  if (list.isError) return <ErrorNotice error={list.error} onRetry={() => void list.refetch()} />;

  return (
    <FlatList
      data={people}
      keyExtractor={(p) => p.nickname}
      contentContainerStyle={styles.list}
      renderItem={({ item }) => (
        <PersonRow
          person={item}
          kind={kind}
          onAction={(accept) =>
            action.mutate(
              { nickname: item.nickname, accept },
              {
                onSuccess: () => {
                  if (kind === "requests") toast.show(accept ? t("@{nick} ora ti segue.", { nick: item.nickname }) : t("Richiesta rifiutata."));
                  if (kind === "blocks") toast.show(t("@{nick} sbloccato.", { nick: item.nickname }));
                },
              },
            )
          }
        />
      )}
      ListEmptyComponent={<EmptyState title={t(EMPTY[kind].title)} body={t(EMPTY[kind].body)} />}
      onEndReached={() => {
        if (list.hasNextPage && !list.isFetchingNextPage) void list.fetchNextPage();
      }}
    />
  );
}

function PersonRow({
  person,
  kind,
  onAction,
}: {
  person: PersonSummary;
  kind: PeopleKind;
  onAction: (accept?: boolean) => void;
}) {
  const open = () => router.push({ pathname: "/user/[nickname]", params: { nickname: person.nickname } });
  return (
    <View style={styles.row}>
      <Pressable
        role="link"
        aria-label={t("Apri il profilo di @{nick}", { nick: person.nickname })}
        onPress={open}
        disabled={kind === "blocks"}
        style={styles.who}
      >
        <Avatar nickname={person.nickname} avatar={person.avatar} size={40} />
        <View style={styles.flex}>
          <Text style={styles.nick} numberOfLines={1}>
            @{person.nickname}
          </Text>
          {person.account_type === "business" ? <Text style={styles.meta}>{t("BUSINESS")}</Text> : null}
        </View>
      </Pressable>
      {kind === "requests" ? (
        <View style={styles.actions}>
          <Button label={t("Accetta")} size="sm" onPress={() => onAction(true)} hint={t("Accetta @{nick}", { nick: person.nickname })} />
          <IconButton label={t("Rifiuta @{nick}", { nick: person.nickname })} onPress={() => onAction(false)}>
            <IconClose color={colors.textSecondary} size={20} />
          </IconButton>
        </View>
      ) : (
        <Button
          label={t({ followers: N_("Rimuovi"), following: N_("Non seguire più"), blocks: N_("Sblocca") }[kind])}
          variant="secondary"
          size="sm"
          onPress={() => onAction()}
          hint={`@${person.nickname}`}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 4, minHeight: 52 },
  title: { flex: 1, textAlign: "center", fontFamily: fonts.display, fontSize: 20, color: colors.text },
  spacer: { width: 44 },
  tabsBar: { flexGrow: 0, borderBottomWidth: 1, borderBottomColor: colors.divider },
  tabs: { gap: 22, paddingHorizontal: spacing[4] },
  tab: { height: 42, justifyContent: "center", borderBottomWidth: 2, borderBottomColor: "transparent" },
  tabOn: { borderBottomColor: colors.accent },
  tabText: { fontFamily: fonts.uiBold, fontSize: 14, color: colors.textSecondary },
  tabTextOn: { color: colors.text },
  list: { padding: spacing[4], gap: spacing[2], flexGrow: 1 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing[2],
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  who: { flex: 1, flexDirection: "row", alignItems: "center", gap: 10, minWidth: 0 },
  flex: { flex: 1, minWidth: 0 },
  nick: { fontFamily: fonts.uiBold, fontSize: 15, color: colors.text },
  meta: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.2, color: colors.textSecondary, marginTop: 2 },
  actions: { flexDirection: "row", alignItems: "center", gap: 2 },
});
