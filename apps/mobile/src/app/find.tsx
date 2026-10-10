import type { UserProfile } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";

import { userKey } from "@/features/portfolio/api";
import { accountTypeLabel } from "@/features/portfolio/format";
import { FollowButton } from "@/features/social/FollowButton";
import { ApiError, apiGet } from "@/lib/api";
import { nicknameHint } from "@/lib/validation";
import { Avatar } from "@/ui/Avatar";
import { Button } from "@/ui/Button";
import { IconButton } from "@/ui/IconButton";
import { IconBack } from "@/ui/icons";
import { TextField } from "@/ui/TextField";

/**
 * Trova un amico con il nickname ESATTO. Non è una ricerca di utenti (sez. 6: in v1 niente
 * elenchi di persone): o il nickname esiste ed è visibile, o "nessun profilo".
 */
export default function FindScreen() {
  const { session } = useAuth();
  const token = session?.access_token;
  const [text, setText] = useState("");
  const [asked, setAsked] = useState("");
  const nickname = asked.trim().replace(/^@/, "").toLowerCase();

  const result = useQuery({
    queryKey: userKey(session?.user.id, nickname),
    queryFn: ({ signal }) => apiGet<UserProfile>(`/v1/users/${encodeURIComponent(nickname)}`, { token, signal }),
    enabled: Boolean(token) && nicknameHint(nickname) === "ok",
    retry: false,
  });

  const submit = () => setAsked(text);
  const invalid = asked !== "" && nicknameHint(nickname) !== "ok";
  const missing = result.error instanceof ApiError && result.error.status === 404;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <IconButton label="Indietro" onPress={() => (router.canGoBack() ? router.back() : router.replace("/profile"))}>
          <IconBack color={colors.text} />
        </IconButton>
        <Text style={styles.title} role="heading">
          Trova persone
        </Text>
        <View style={styles.spacer} />
      </View>
      <View style={styles.body}>
        <Text style={styles.intro}>
          Scrivi il nickname esatto di un amico. Su WearX non ci sono elenchi di persone da sfogliare.
        </Text>
        <View style={styles.searchRow}>
          <View style={styles.flex}>
            <TextField
              label="Nickname"
              prefix="@"
              value={text}
              onChangeText={setText}
              autoCapitalize="none"
              autoCorrect={false}
              returnKeyType="search"
              onSubmitEditing={submit}
              error={invalid ? "Questo non è un nickname valido." : null}
            />
          </View>
          <View style={styles.go}>
            <Button label="Cerca" size="md" onPress={submit} disabled={!text.trim()} loading={result.isFetching} />
          </View>
        </View>

        {missing ? <Text style={styles.none}>Nessun profilo con questo nickname.</Text> : null}
        {result.data ? <Result user={result.data} /> : null}
      </View>
    </SafeAreaView>
  );
}

function Result({ user }: { user: UserProfile }) {
  const open = () =>
    user.is_self
      ? router.navigate("/profile")
      : router.push({ pathname: "/user/[nickname]", params: { nickname: user.nickname } });
  return (
    <View style={styles.card}>
      <Pressable role="link" aria-label={`Apri il profilo di @${user.nickname}`} onPress={open} style={styles.who}>
        <View style={styles.avatar} aria-hidden>
          <Avatar nickname={user.nickname} avatar={user.avatar} size={43} />
        </View>
        <View style={styles.flex}>
          <Text style={styles.nick}>@{user.nickname}</Text>
          <Text style={styles.meta}>
            {accountTypeLabel(user.account_type)} · {user.stats.posts} fit · {user.followers} follower
          </Text>
        </View>
      </Pressable>
      {user.is_self ? <Text style={styles.meta}>Sei tu.</Text> : <FollowButton user={user} />}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 4, minHeight: 52 },
  title: { flex: 1, textAlign: "center", fontFamily: fonts.display, fontSize: 20, color: colors.text },
  spacer: { width: 44 },
  body: { padding: spacing[4], gap: spacing[4] },
  intro: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.textSecondary },
  searchRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing[2] },
  flex: { flex: 1, minWidth: 0 },
  go: { paddingTop: 22 },
  none: { fontFamily: fonts.ui, fontSize: 14, color: colors.textTertiary },
  card: {
    gap: spacing[3],
    padding: spacing[4],
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.surface,
  },
  who: { flexDirection: "row", alignItems: "center", gap: 12 },
  avatar: {
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 1.5,
    borderColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  nick: { fontFamily: fonts.uiBold, fontSize: 16, color: colors.text },
  meta: { fontFamily: fonts.ui, fontSize: 13, color: colors.textSecondary, marginTop: 2 },
});
