import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { useDeletion } from "@/features/privacy/api";
import { ApiError } from "@/lib/api";
import { Button } from "@/ui/Button";
import { TextField } from "@/ui/TextField";
import { TopBar } from "@/ui/TopBar";

const ERRORS: Record<string, string> = {
  "deletion.confirm_mismatch": "Il nickname non corrisponde.",
  "deletion.suspended": "Durante una sospensione l'account non si può cancellare: scrivi al supporto.",
};

/** Cancella l'account: 30 giorni per ripensarci, poi è definitivo. */
export default function DeleteAccountScreen() {
  const { profile } = useAuth();
  const { request } = useDeletion();
  const [typed, setTyped] = useState("");
  const nickname = profile?.nickname ?? "";
  const matches = typed.trim().replace(/^@/, "").toLowerCase() === nickname.toLowerCase() && nickname !== "";
  const code = request.error instanceof ApiError ? request.error.code : null;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title="Cancella l'account" fallback="/settings" />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.lead}>Cosa succede</Text>
        <Step n="1" title="Subito">
          Il tuo profilo, i fit e le capsule spariscono per tutti. Esci da tutti i dispositivi e non ricevi più
          notifiche.
        </Step>
        <Step n="2" title="Per 30 giorni">
          Puoi ripensarci: accedi con email e password e tocca «Annulla la cancellazione». Tutto torna com&apos;era.
        </Step>
        <Step n="3" title="Dopo 30 giorni">
          Cancelliamo per sempre profilo, foto, fit, follow, notifiche e accesso. Non si può tornare indietro.
        </Step>
        <View style={styles.box}>
          <Text style={styles.boxText}>
            Restano, senza alcun collegamento con te: i voti che hai dato (anonimi, dentro le medie dei fit altrui) e
            le decisioni della moderazione (per legge). Prima di cancellare puoi{" "}
            <Text style={styles.link} role="link" onPress={() => router.push("/data-export")}>
              scaricare i tuoi dati
            </Text>
            .
          </Text>
        </View>
        <TextField
          label={`SCRIVI @${nickname.toUpperCase()} PER CONFERMARE`}
          value={typed}
          onChangeText={setTyped}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder={`@${nickname}`}
          error={code ? (ERRORS[code] ?? "Non è riuscito. Riprova.") : null}
        />
        <Button
          label="Cancella il mio account"
          variant="danger"
          fullWidth
          disabled={!matches}
          loading={request.isPending}
          onPress={() => request.mutate(typed)}
        />
        <Button label="Ci ripenso" variant="ghost" fullWidth onPress={() => router.back()} />
      </ScrollView>
    </SafeAreaView>
  );
}

function Step({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <View style={styles.step}>
      <Text style={styles.stepN}>{n}</Text>
      <View style={styles.stepText}>
        <Text style={styles.stepTitle}>{title}</Text>
        <Text style={styles.text}>{children}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], gap: spacing[4], paddingBottom: spacing[8] },
  lead: { fontFamily: fonts.display, fontSize: 24, color: colors.text },
  step: { flexDirection: "row", gap: spacing[3] },
  stepN: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.border,
    textAlign: "center",
    lineHeight: 26,
    fontFamily: fonts.numericBold,
    fontSize: 12,
    color: colors.text,
  },
  stepText: { flex: 1, gap: 3 },
  stepTitle: { fontFamily: fonts.uiSemiBold, fontSize: 15, color: colors.text },
  text: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textSecondary },
  box: { padding: spacing[3], borderRadius: radii.sm, backgroundColor: colors.surface },
  boxText: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textSecondary },
  link: { color: colors.text, textDecorationLine: "underline" },
});
