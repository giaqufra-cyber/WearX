import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { useUpdateProfile } from "@/features/privacy/api";
import { Button } from "@/ui/Button";
import { SegmentedControl } from "@/ui/SegmentedControl";
import { Sheet } from "@/ui/Sheet";
import { TopBar } from "@/ui/TopBar";
import { useToast } from "@/ui/Toast";

type Kind = "private" | "business";

const POINTS: Record<Kind, string[]> = {
  private: [
    "I tuoi fit li vedono solo le persone che approvi.",
    "Nel feed degli altri i tuoi fit sono anonimi.",
    "Per chi crea il proprio archivio di stile.",
  ],
  business: [
    "Profilo pubblico: tutti vedono i tuoi fit e il tuo nome.",
    "Ti seguono senza richiesta (le richieste in attesa diventano follow).",
    "Puoi verificare il sito del tuo negozio: i tuoi capi mostrano «negozio verificato».",
    "Negli Insight vedi i click verso il tuo negozio.",
  ],
};

/** Privato o Business (solo maggiorenni). */
export default function AccountTypeScreen() {
  const { profile } = useAuth();
  const toast = useToast();
  const update = useUpdateProfile();
  const current: Kind = profile?.account_type ?? "private";
  const [choice, setChoice] = useState<Kind>(current);
  const [confirm, setConfirm] = useState(false);
  const adult = profile?.age_band === "18_plus";

  const save = () =>
    update.mutate(
      { account_type: choice },
      {
        onSuccess: () => {
          setConfirm(false);
          toast.show(choice === "business" ? "Ora sei un account Business." : "Ora il tuo account è privato.");
          if (choice === "business") router.replace("/shop-domains");
        },
        onError: () => {
          setConfirm(false);
          toast.show("Non è riuscito. Riprova.", { tone: "error" });
        },
      },
    );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title="Tipo di account" fallback="/settings" />
      <ScrollView contentContainerStyle={styles.content}>
        {!adult ? (
          <Text style={styles.text}>Gli account Business sono per maggiorenni: il tuo account resta privato.</Text>
        ) : (
          <>
            <SegmentedControl
              label="Tipo di account"
              options={[
                { value: "private", label: "Privato" },
                { value: "business", label: "Business" },
              ]}
              value={choice}
              onChange={setChoice}
            />
            <View style={styles.card}>
              <Text style={styles.cardTitle}>{choice === "business" ? "Business" : "Privato"}</Text>
              {POINTS[choice].map((line) => (
                <Text key={line} style={styles.point}>
                  — {line}
                </Text>
              ))}
            </View>
            {choice !== current ? (
              <Button
                label={choice === "business" ? "Passa a Business" : "Torna privato"}
                fullWidth
                onPress={() => setConfirm(true)}
              />
            ) : (
              <Text style={styles.text}>Questo è il tuo tipo di account attuale.</Text>
            )}
          </>
        )}
      </ScrollView>
      <Sheet
        visible={confirm}
        title={choice === "business" ? "Passare a Business?" : "Tornare privato?"}
        onClose={() => setConfirm(false)}
      >
        <Text style={styles.text}>
          {choice === "business"
            ? "Il tuo profilo e i tuoi fit diventano visibili a tutti. Puoi tornare privato quando vuoi."
            : "Chi ti segue già continua a seguirti; i nuovi dovranno chiedere. I siti verificati vengono tolti."}
        </Text>
        <Button label="Conferma" fullWidth loading={update.isPending} onPress={save} />
        <Button label="Annulla" variant="ghost" fullWidth onPress={() => setConfirm(false)} />
      </Sheet>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], gap: spacing[4], paddingBottom: spacing[8] },
  card: {
    gap: spacing[2],
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.surface,
  },
  cardTitle: { fontFamily: fonts.display, fontSize: 22, color: colors.text },
  point: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 21, color: colors.textMuted },
  text: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 21, color: colors.textSecondary },
});
