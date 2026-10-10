import type { ModerationNotice } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { APPEAL_STATUS, appealError, noticeTitle, useAppeal, useNotices } from "@/features/moderation/api";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { TextField } from "@/ui/TextField";

const dateLabel = (iso: string) =>
  new Date(iso).toLocaleDateString("it-IT", { day: "numeric", month: "long", year: "numeric" });

/** Ogni decisione della moderazione che ti riguarda, con il motivo e il reclamo (art. 17 e 20 DSA). */
export function NoticeList({ canOpenPosts = true }: { canOpenPosts?: boolean }) {
  const notices = useNotices();
  if (notices.isPending) return <Loading label="Carico gli avvisi" />;
  if (notices.isError) return <ErrorNotice error={notices.error} onRetry={() => void notices.refetch()} />;
  if (notices.data.length === 0) {
    return <EmptyState title="Nessun avviso" body="Qui trovi le decisioni della moderazione che ti riguardano." />;
  }
  return (
    <View style={styles.list}>
      {notices.data.map((n) => (
        <NoticeCard key={n.id} notice={n} canOpenPost={canOpenPosts} />
      ))}
    </View>
  );
}

function NoticeCard({ notice, canOpenPost }: { notice: ModerationNotice; canOpenPost: boolean }) {
  const appeal = useAppeal();
  const [writing, setWriting] = useState(false);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const restored = notice.action === "restore";

  return (
    <View style={[styles.card, restored && styles.cardOk]} role="article" aria-label={noticeTitle(notice)}>
      <View style={styles.head}>
        <Text style={[styles.title, restored && styles.titleOk]}>{noticeTitle(notice)}</Text>
        <Text style={styles.date}>{dateLabel(notice.created_at)}</Text>
      </View>
      <Text style={styles.meta}>
        {notice.automated ? "DECISIONE AUTOMATICA" : "DECISIONE DI UN MODERATORE"} · {notice.reason.toUpperCase()}
      </Text>
      <Text style={styles.statement}>{notice.statement}</Text>

      {notice.appeal ? (
        <View style={styles.appeal}>
          <Text style={styles.appealStatus}>{APPEAL_STATUS[notice.appeal.status]}</Text>
          {notice.appeal.decision_note ? <Text style={styles.appealNote}>{notice.appeal.decision_note}</Text> : null}
        </View>
      ) : null}

      {notice.post_id && canOpenPost ? (
        <Button
          label="Apri il fit"
          variant="ghost"
          size="sm"
          onPress={() => router.push({ pathname: "/post/[id]", params: { id: notice.post_id! } })}
        />
      ) : null}

      {notice.can_appeal && !writing ? (
        <Button label="Fai reclamo" variant="secondary" size="sm" onPress={() => setWriting(true)} />
      ) : null}
      {writing ? (
        <View style={styles.form}>
          <TextField
            label="Il tuo reclamo"
            value={text}
            onChangeText={(value) => {
              setText(value);
              setError(null);
            }}
            multiline
            maxLength={1000}
            placeholder="Spiega perché pensi che sia un errore"
            hint="Lo legge un moderatore diverso da chi ha deciso."
            error={error}
          />
          <View style={styles.row}>
            <Button label="Annulla" variant="ghost" size="sm" onPress={() => setWriting(false)} />
            <Button
              label="Invia reclamo"
              size="sm"
              disabled={!text.trim()}
              loading={appeal.isPending}
              onPress={() =>
                appeal.mutate(
                  { actionId: notice.id, text: text.trim() },
                  { onSuccess: () => setWriting(false), onError: (e) => setError(appealError(e)) },
                )
              }
            />
          </View>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: spacing[3] },
  card: {
    gap: spacing[2],
    padding: spacing[4],
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  cardOk: { borderColor: colors.borderSubtle },
  head: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", gap: spacing[2] },
  title: { fontFamily: fonts.display, fontSize: 20, color: colors.warning, flexShrink: 1 },
  titleOk: { color: colors.accent },
  date: { fontFamily: fonts.mono, fontSize: 11, color: colors.textSecondary },
  meta: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1, color: colors.textTertiary },
  statement: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.textMuted },
  appeal: { gap: 2, paddingTop: spacing[1] },
  appealStatus: { fontFamily: fonts.uiBold, fontSize: 13, color: colors.text },
  appealNote: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 18, color: colors.textSecondary },
  form: { gap: spacing[2] },
  row: { flexDirection: "row", justifyContent: "flex-end", gap: spacing[2] },
});
