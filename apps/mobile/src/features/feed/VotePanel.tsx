import type { Post } from "@wearx/api-types";
import { colors, fonts, radii, spacing, voteMood } from "@wearx/design-tokens";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { statsNote, votesLabel } from "@/features/feed/format";
import { VoteSlider } from "@/features/feed/VoteSlider";
import { Button } from "@/ui/Button";

type Props = {
  post: Post;
  onVote: (score: number, styleConfirm: boolean | null) => void;
  busy: boolean;
};

export const DEFAULT_DRAFT = 70;

/** Voto (prototipo): prima di votare lo slider; dopo, la media della community e il tuo voto. */
export function VotePanel({ post, onVote, busy }: Props) {
  const [draft, setDraft] = useState(DEFAULT_DRAFT);
  const [confirm, setConfirm] = useState<boolean | null>(null);
  const { vote } = post;

  if (post.is_own || vote.mine !== null) {
    const average = vote.average;
    return (
      <View style={styles.wrap}>
        <View style={styles.head}>
          <View style={styles.flex}>
            <Text style={styles.kicker}>{post.is_own ? "IL TUO FIT · MEDIA" : "MEDIA COMMUNITY"}</Text>
            <Text style={styles.meta}>
              {vote.vote_count !== null ? votesLabel(vote.vote_count) : "Media dei voti"}
              {vote.mine !== null ? (
                <>
                  {" · il tuo "}
                  <Text style={styles.mine}>{vote.mine}</Text>
                </>
              ) : null}
            </Text>
          </View>
          <Text
            style={styles.score}
            aria-label={average === null ? "Media non ancora disponibile" : `Media ${average}`}
          >
            {average === null ? (busy ? "…" : "—") : Math.round(average)}
          </Text>
        </View>
        <View style={styles.bar}>
          {average !== null ? <View style={[styles.barFill, { width: `${average}%` }]} /> : null}
          {vote.mine !== null ? <View style={[styles.marker, { left: `${vote.mine}%` }]} /> : null}
        </View>
        <Text style={styles.note}>{statsNote(vote)}</Text>
      </View>
    );
  }

  return (
    <View style={styles.wrap}>
      <View style={styles.head}>
        <View style={styles.flex}>
          <Text style={styles.kicker}>VOTA IL FIT · 1–100</Text>
          <Text style={styles.mood}>{voteMood(draft)}</Text>
        </View>
        <Text style={styles.score} aria-live="polite">
          {draft}
        </Text>
      </View>
      {vote.ask_style_confirm ? (
        <View style={styles.confirm}>
          <Text style={styles.confirmText}>
            È davvero <Text style={styles.styleName}>{post.style.name}</Text>?
          </Text>
          <View style={styles.choices} role="radiogroup" aria-label={`È davvero ${post.style.name}?`}>
            {([true, false] as const).map((answer) => (
              <Pressable
                key={String(answer)}
                role="radio"
                aria-checked={confirm === answer}
                onPress={() => setConfirm(confirm === answer ? null : answer)}
                style={[styles.choice, confirm === answer ? styles.choiceOn : null]}
              >
                <Text style={[styles.choiceText, confirm === answer ? styles.choiceTextOn : null]}>
                  {answer ? "Sì" : "No"}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}
      <View style={styles.controls}>
        <VoteSlider value={draft} onChange={setDraft} color={colors.accent} label="Il tuo voto da 1 a 100" />
        <Button label="Vota" variant="inverse" size="md" onPress={() => onVote(draft, confirm)} loading={busy} />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { paddingHorizontal: spacing[4], paddingTop: spacing[3] },
  head: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", gap: spacing[3] },
  flex: { flex: 1 },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 11 * 0.14, color: colors.textSecondary },
  mood: { fontFamily: fonts.uiSemiBold, fontSize: 16, color: colors.text, marginTop: 4 },
  meta: { fontFamily: fonts.ui, fontSize: 13, color: colors.textSecondary, marginTop: 5 },
  mine: { fontFamily: fonts.uiBold, color: colors.text },
  score: {
    fontFamily: fonts.numeric,
    fontSize: 50,
    lineHeight: 50,
    color: colors.accent,
    fontVariant: ["tabular-nums"],
  },
  controls: { flexDirection: "row", alignItems: "center", gap: spacing[2], marginTop: spacing[2] },
  confirm: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing[3],
    paddingVertical: spacing[2],
    paddingHorizontal: spacing[3],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
  },
  confirmText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textMuted, flex: 1 },
  styleName: { fontFamily: fonts.display, fontSize: 15, color: colors.text },
  choices: { flexDirection: "row", gap: 6 },
  choice: {
    minWidth: 48,
    height: 32,
    paddingHorizontal: 12,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  choiceOn: { backgroundColor: colors.inverse, borderColor: colors.inverse },
  choiceText: { fontFamily: fonts.uiBold, fontSize: 13, color: colors.text },
  choiceTextOn: { color: colors.onInverse },
  note: { fontFamily: fonts.ui, fontSize: 12, color: colors.textMuted, marginTop: spacing[2] },
  bar: { height: 6, borderRadius: 3, backgroundColor: "#26262A", marginTop: 14 },
  barFill: { position: "absolute", left: 0, top: 0, bottom: 0, borderRadius: 3, backgroundColor: colors.accent },
  marker: { position: "absolute", top: -5, width: 2, height: 16, marginLeft: -1, backgroundColor: colors.inverse },
});
