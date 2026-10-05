import type { Post } from "@wearx/api-types";
import { colors, fonts, spacing } from "@wearx/design-tokens";
import { router, useLocalSearchParams } from "expo-router";
import { useCallback, useEffect, useState } from "react";
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { useVote } from "@/features/feed/api";
import { PostCard } from "@/features/feed/PostCard";
import { useCapsules, useMoveFit, usePortfolio, usePost, usePostActions } from "@/features/portfolio/api";
import { CapsulePicker } from "@/features/portfolio/CapsulePicker";
import { ApiError } from "@/lib/api";
import { track } from "@/lib/events";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { IconButton } from "@/ui/IconButton";
import { IconBack, IconFolder, IconStar, IconTrash } from "@/ui/icons";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { Sheet } from "@/ui/Sheet";
import { useToast } from "@/ui/Toast";

const MAX_WIDTH = 560;

/** Un fit a tutto schermo; se è tuo: capsula, copertina, elimina. */
export default function PostScreen() {
  const { id = "", from } = useLocalSearchParams<{ id: string; from?: string }>();
  const post = usePost(id);
  const loaded = post.data?.id;
  useEffect(() => {
    if (loaded) track({ name: "post_open", post_id: loaded, source: from === "style" || from === "feed" ? from : "profile" });
  }, [loaded, from]);
  const toast = useToast();
  const vote = useVote({ onError: (message) => toast.show(message, { tone: "error" }) });
  const { width: screen } = useWindowDimensions();
  const width = Math.min(screen, MAX_WIDTH);
  const onVote = useCallback(
    (p: Post, score: number, styleConfirm: boolean | null) => vote.mutate({ postId: p.id, score, styleConfirm }),
    [vote],
  );
  const back = () => (router.canGoBack() ? router.back() : router.replace("/profile"));

  let body;
  if (post.isPending) body = <Loading label="Carico il fit" />;
  else if (post.isError) {
    body =
      post.error instanceof ApiError && post.error.status === 404 ? (
        <EmptyState title="Fit non disponibile" body="È stato eliminato o non è più visibile." />
      ) : (
        <ErrorNotice error={post.error} onRetry={() => void post.refetch()} />
      );
  } else {
    body = (
      <>
        <PostCard post={post.data} width={width} onVote={onVote} voting={vote.isPending} />
        {post.data.is_own ? <OwnerActions post={post.data} onDeleted={back} /> : null}
      </>
    );
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <IconButton label="Indietro" onPress={back}>
          <IconBack color={colors.text} />
        </IconButton>
        <Text style={styles.title} role="heading">
          {post.data?.is_own ? "Il tuo fit" : "Il fit"}
        </Text>
        <View style={styles.headerSpacer} />
      </View>
      <ScrollView contentContainerStyle={[styles.content, { width }]}>{body}</ScrollView>
    </SafeAreaView>
  );
}

function OwnerActions({ post, onDeleted }: { post: Post; onDeleted: () => void }) {
  const { profile } = useAuth();
  const nickname = profile?.nickname ?? "";
  const toast = useToast();
  const capsules = useCapsules();
  const portfolio = usePortfolio(nickname, null);
  const move = useMoveFit(nickname, { onError: (message) => toast.show(message, { tone: "error" }) });
  const { setCapsule, remove } = usePostActions(post.id);
  const [picking, setPicking] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const capsuleName = capsules.data?.find((c) => c.id === post.capsule_id)?.name ?? null;
  const isCover = portfolio.data?.pages[0]?.cover_id === post.id;

  return (
    <View style={styles.actions}>
      {post.status === "hidden_moderation" ? (
        <View style={styles.hidden} role="alert">
          <Text style={styles.hiddenTitle}>Nascosto dalla moderazione</Text>
          <Text style={styles.hiddenText}>Gli altri non lo vedono. Trovi il motivo e puoi fare reclamo.</Text>
          <Button label="Vedi il motivo" variant="secondary" size="sm" onPress={() => router.push("/moderation")} />
        </View>
      ) : null}
      <Text style={styles.kicker}>IL TUO PORTFOLIO</Text>
      <Button
        label={capsuleName ? `Capsula: ${capsuleName}` : "Aggiungi a una capsula"}
        variant="secondary"
        size="md"
        fullWidth
        icon={<IconFolder color={colors.text} />}
        onPress={() => setPicking(true)}
      />
      <Button
        label={isCover ? "È la copertina del portfolio" : "Metti in copertina"}
        variant="secondary"
        size="md"
        fullWidth
        disabled={isCover}
        loading={move.isPending}
        icon={<IconStar color={isCover ? colors.accent : colors.text} />}
        onPress={() =>
          move.mutate(
            { postId: post.id, afterId: null },
            { onSuccess: () => toast.show("Ora è la copertina del tuo portfolio.") },
          )
        }
      />
      <Button
        label="Elimina fit"
        variant="ghost"
        size="md"
        fullWidth
        icon={<IconTrash color={colors.danger} />}
        onPress={() => setConfirmDelete(true)}
      />

      <CapsulePicker
        visible={picking}
        current={post.capsule_id ?? null}
        busy={setCapsule.isPending}
        onClose={() => setPicking(false)}
        onPick={(capsuleId) =>
          setCapsule.mutate(capsuleId, {
            onSuccess: () => {
              setPicking(false);
              toast.show(capsuleId ? "Fit aggiunto alla capsula." : "Fit tolto dalla capsula.");
            },
            onError: () => toast.show("Non riusciamo a salvare. Riprova.", { tone: "error" }),
          })
        }
      />
      <Sheet visible={confirmDelete} title="Eliminare il fit?" onClose={() => setConfirmDelete(false)}>
        <Text style={styles.sheetText}>Foto, capi e voti spariscono per sempre. Non si può annullare.</Text>
        <View style={styles.sheetButtons}>
          <View style={styles.flex}>
            <Button label="Annulla" variant="secondary" size="md" fullWidth onPress={() => setConfirmDelete(false)} />
          </View>
          <View style={styles.flex}>
            <Button
              label="Elimina"
              variant="danger"
              size="md"
              fullWidth
              loading={remove.isPending}
              onPress={() =>
                remove.mutate(undefined, {
                  onSuccess: () => {
                    setConfirmDelete(false);
                    toast.show("Fit eliminato.");
                    onDeleted();
                  },
                  onError: () => toast.show("Non riusciamo a eliminarlo. Riprova.", { tone: "error" }),
                })
              }
            />
          </View>
        </View>
      </Sheet>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 4, minHeight: 52 },
  title: { flex: 1, textAlign: "center", fontFamily: fonts.display, fontSize: 20, color: colors.text },
  headerSpacer: { width: 44 },
  content: { alignSelf: "center", paddingBottom: spacing[8] },
  actions: { paddingHorizontal: spacing[4], paddingTop: spacing[5], gap: spacing[2] },
  hidden: {
    gap: spacing[2],
    padding: spacing[4],
    marginBottom: spacing[3],
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.warning,
  },
  hiddenTitle: { fontFamily: fonts.uiBold, fontSize: 15, color: colors.warning },
  hiddenText: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 18, color: colors.textSecondary },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5, color: colors.textSecondary, marginBottom: 2 },
  sheetText: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.textSecondary },
  sheetButtons: { flexDirection: "row", gap: spacing[2] },
  flex: { flex: 1 },
});
