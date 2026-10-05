import { colors, fonts, spacing } from "@wearx/design-tokens";
import { StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { longDate, useDeletion, useDeletionStatus } from "@/features/privacy/api";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { useToast } from "@/ui/Toast";

/** Account in cancellazione: unica schermata raggiungibile finché non si annulla o si esce. */
export default function DeletingScreen() {
  const { signOut, profile } = useAuth();
  const status = useDeletionStatus();
  const { cancel } = useDeletion();
  const toast = useToast();
  const when = status.data?.delete_after;

  return (
    <Screen scroll={false}>
      <View style={styles.body}>
        <Text style={styles.kicker}>ACCOUNT IN CANCELLAZIONE</Text>
        <Text style={styles.title} role="heading">
          @{profile?.nickname}
        </Text>
        <Text style={styles.text}>
          {when
            ? `Il tuo account verrà cancellato per sempre il ${longDate(when)}. Fino ad allora nessuno vede il tuo profilo e i tuoi fit.`
            : "Il tuo account è in cancellazione. Nessuno vede il tuo profilo e i tuoi fit."}
        </Text>
        <Text style={styles.text}>Ci hai ripensato? Annulla e tutto torna com&apos;era.</Text>
      </View>
      <View style={styles.actions}>
        <Button
          label="Annulla la cancellazione"
          fullWidth
          loading={cancel.isPending}
          onPress={() =>
            cancel.mutate(undefined, {
              onSuccess: () => toast.show("Bentornato! Il tuo account è di nuovo attivo."),
              onError: () => toast.show("Non è riuscito. Riprova.", { tone: "error" }),
            })
          }
        />
        <Button label="Esci" variant="ghost" fullWidth onPress={() => void signOut()} />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: { flex: 1, justifyContent: "center", gap: spacing[3] },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5, color: colors.danger },
  title: { fontFamily: fonts.display, fontSize: 34, color: colors.text },
  text: { fontFamily: fonts.ui, fontSize: 15, lineHeight: 22, color: colors.textSecondary },
  actions: { gap: spacing[2], paddingBottom: spacing[4] },
});
