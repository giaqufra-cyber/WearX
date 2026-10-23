import type { UserProfile } from "@wearx/api-types";
import { colors, fonts, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { followLabel, useFollow } from "@/features/social/api";
import { Button } from "@/ui/Button";
import { Sheet } from "@/ui/Sheet";
import { useToast } from "@/ui/Toast";
import { t } from "@/lib/i18n";

/** Segui / Richiesta inviata / Segui già, con conferma prima di perdere l'accesso a un privato. */
export function FollowButton({ user }: { user: UserProfile }) {
  const toast = useToast();
  const follow = useFollow(user.nickname, { onError: (message) => toast.show(message, { tone: "error" }) });
  const [confirm, setConfirm] = useState(false);
  const state = user.relationship.following;
  const isPrivate = user.account_type === "private";

  const press = () => {
    if (state === "none") {
      follow.mutate("follow", {
        onSuccess: (now) =>
          toast.show(now === "pending" ? t("Richiesta inviata a @{nickname}.", { nickname: user.nickname }) : t("Ora segui @{nickname}.", { nickname: user.nickname })),
      });
    } else if (state === "pending") {
      follow.mutate("unfollow", { onSuccess: () => toast.show(t("Richiesta ritirata.")) });
    } else if (isPrivate) {
      setConfirm(true);
    } else {
      follow.mutate("unfollow");
    }
  };

  return (
    <>
      <Button
        label={followLabel(state, user.relationship.follows_you)}
        variant={state === "none" ? "primary" : "secondary"}
        size="md"
        fullWidth
        onPress={press}
        hint={state === "pending" ? t("Tocca per ritirare la richiesta") : state === "accepted" ? t("Tocca per smettere di seguire") : undefined}
      />
      <Sheet visible={confirm} title={t("Smettere di seguire @{nickname}?", { nickname: user.nickname })} onClose={() => setConfirm(false)}>
        <Text style={styles.text}>
          {t("L'account è privato: non vedrai più il suo portfolio finché non ti accetta di nuovo.")}
        </Text>
        <View style={styles.row}>
          <View style={styles.flex}>
            <Button label={t("Annulla")} variant="secondary" size="md" fullWidth onPress={() => setConfirm(false)} />
          </View>
          <View style={styles.flex}>
            <Button
              label={t("Smetti di seguire")}
              variant="danger"
              size="md"
              fullWidth
              onPress={() => {
                setConfirm(false);
                follow.mutate("unfollow");
              }}
            />
          </View>
        </View>
      </Sheet>
    </>
  );
}

const styles = StyleSheet.create({
  text: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.textSecondary },
  row: { flexDirection: "row", gap: spacing[2] },
  flex: { flex: 1 },
});
