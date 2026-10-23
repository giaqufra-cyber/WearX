import type { StyleProposal } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { FlatList, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { CATEGORIES } from "@/features/styles/catalog";
import { progress, proposalError, useProposals, useSupport } from "@/features/styles/proposals";
import { ProposeSheet } from "@/features/styles/ProposeSheet";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { SearchField } from "@/ui/SearchField";
import { TopBar } from "@/ui/TopBar";
import { useToast } from "@/ui/Toast";
import { N_, t } from "@/lib/i18n";

const categoryLabel = (key: string) => CATEGORIES.find((c) => c.key === key)?.label ?? N_("Stili");

/** Stili proposti dalla community: chi ne vuole uno nuovo lo propone, gli altri lo chiedono. */
export default function StyleProposalsScreen() {
  const params = useLocalSearchParams<{ name?: string }>();
  const [query, setQuery] = useState("");
  const [proposing, setProposing] = useState(Boolean(params.name));
  const debounced = useDebouncedValue(query.trim(), 250);
  const list = useProposals(debounced);
  const support = useSupport();
  const toast = useToast();

  const toggle = (proposal: StyleProposal) =>
    support.mutate(
      { id: proposal.id, on: !proposal.supported },
      {
        onSuccess: (updated) => {
          if (updated.status === "approved") {
            toast.show(t("«{name}» ora è uno stile. Ci sei dentro.", { name: updated.name }));
            if (updated.style) router.push({ pathname: "/style/[slug]", params: { slug: updated.style } });
          }
        },
        onError: (error) => toast.show(proposalError(error), { tone: "error" }),
      },
    );

  const items = list.data?.items ?? [];
  const threshold = list.data?.threshold;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title={t("Stili proposti")} fallback="/explore" />
      <FlatList
        data={items}
        keyExtractor={(p) => p.id}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        ListHeaderComponent={
          <View style={styles.header}>
            <Text style={styles.lead}>
              {threshold ? t("A {threshold} richieste diventa uno stile.", { threshold }) : " "}
            </Text>
            <Button label={t("Proponi uno stile")} onPress={() => setProposing(true)} fullWidth size="md" />
            <SearchField value={query} onChangeText={setQuery} label={t("Cerca tra le proposte")} placeholder={t("Cerca tra le proposte")} />
          </View>
        }
        renderItem={({ item }) => (
          <ProposalRow proposal={item} busy={support.isPending} onToggle={() => toggle(item)} />
        )}
        ListEmptyComponent={
          list.isPending ? (
            <Loading label={t("Carichiamo le proposte…")} />
          ) : list.isError ? (
            <ErrorNotice error={list.error} onRetry={() => void list.refetch()} />
          ) : (
            <EmptyState
              title={debounced ? t("Nessuna proposta con questo nome") : t("Ancora nessuna proposta")}
              body={t("Proponi tu il primo stile che manca.")}
            />
          )
        }
      />
      <ProposeSheet
        visible={proposing}
        initialName={typeof params.name === "string" ? params.name : ""}
        onClose={() => setProposing(false)}
      />
    </SafeAreaView>
  );
}

function ProposalRow({ proposal, busy, onToggle }: { proposal: StyleProposal; busy: boolean; onToggle: () => void }) {
  const { label, ratio } = progress(proposal);
  return (
    <View style={styles.row} accessible={false}>
      <View style={styles.rowText}>
        <Text style={styles.name} numberOfLines={1}>
          {proposal.name}
        </Text>
        <Text style={styles.meta} numberOfLines={1}>
          {t(categoryLabel(proposal.category)).toUpperCase()}
          {proposal.tagline ? ` · ${proposal.tagline}` : ""}
        </Text>
        <View style={styles.bar} role="progressbar" aria-label={t("{name}: {label} richieste", { name: proposal.name, label })}>
          <View style={[styles.fill, { width: `${Math.round(ratio * 100)}%` }]} />
        </View>
        <Text style={styles.count}>{label}</Text>
      </View>
      <Button
        label={proposal.supported ? t("Lo vuoi") : t("Lo voglio")}
        variant={proposal.supported ? "inverse" : "secondary"}
        size="sm"
        disabled={busy}
        hint={proposal.supported ? t("Tocca per ritirare la richiesta per {name}", { name: proposal.name }) : t("Chiedi lo stile {name}", { name: proposal.name })}
        onPress={onToggle}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], gap: spacing[3], maxWidth: 560, width: "100%", alignSelf: "center" },
  header: { gap: spacing[3], marginBottom: spacing[2] },
  lead: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.textSecondary },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing[3],
    padding: spacing[3],
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.surface,
  },
  rowText: { flex: 1, minWidth: 0, gap: 4 },
  name: { fontFamily: fonts.display, fontSize: 22, lineHeight: 26, color: colors.text },
  meta: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.2, color: colors.textSecondary },
  bar: { height: 6, borderRadius: 3, backgroundColor: colors.surfaceRaised, overflow: "hidden", marginTop: 6 },
  fill: { height: 6, borderRadius: 3, backgroundColor: colors.accent },
  count: { fontFamily: fonts.ui, fontSize: 12, color: colors.textTertiary },
});
