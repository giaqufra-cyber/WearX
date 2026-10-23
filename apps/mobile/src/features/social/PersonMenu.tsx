import { colors, fonts, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text } from "react-native";

import { socialError, useBlock } from "@/features/social/api";
import { Button } from "@/ui/Button";
import { Sheet } from "@/ui/Sheet";
import { useToast } from "@/ui/Toast";
import { t } from "@/lib/i18n";

/** Azioni su un'altra persona: segnala, blocca. */
export function PersonMenu({
  nickname,
  visible,
  onClose,
  onReport,
}: {
  nickname: string;
  visible: boolean;
  onClose: () => void;
  onReport: () => void;
}) {
  const toast = useToast();
  const block = useBlock(nickname);
  const [confirm, setConfirm] = useState(false);
  const close = () => {
    setConfirm(false);
    onClose();
  };

  return (
    <Sheet visible={visible} title={`@${nickname}`} onClose={close}>
      {confirm ? (
        <>
          <Text style={styles.text}>
            {t("Non vi vedrete più: profilo, fit e feed. I follow tra voi vengono tolti e non riceve nessun avviso. Puoi sbloccare quando vuoi da Account › Account bloccati.")}
          </Text>
          <Button
            label={t("Blocca @{nickname}", { nickname })}
            variant="danger"
            size="md"
            fullWidth
            loading={block.isPending}
            onPress={() =>
              block.mutate(undefined, {
                onSuccess: () => {
                  close();
                  toast.show(t("@{nick} bloccato.", { nick: nickname }));
                  if (router.canGoBack()) router.back();
                },
                onError: (error) => toast.show(socialError(error), { tone: "error" }),
              })
            }
          />
          <Button label={t("Annulla")} variant="ghost" size="md" fullWidth onPress={() => setConfirm(false)} />
        </>
      ) : (
        <>
          <Button
            label={t("Segnala")}
            variant="secondary"
            size="md"
            fullWidth
            onPress={() => {
              close();
              onReport();
            }}
          />
          <Button label={t("Blocca")} variant="danger" size="md" fullWidth onPress={() => setConfirm(true)} />
        </>
      )}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  text: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.textSecondary, marginBottom: spacing[1] },
});
