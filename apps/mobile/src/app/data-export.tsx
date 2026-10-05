import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import * as WebBrowser from "expo-web-browser";
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { formatBytes, longDate, useExport, useRequestExport } from "@/features/privacy/api";
import { ApiError } from "@/lib/api";
import { Button } from "@/ui/Button";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { TopBar } from "@/ui/TopBar";

const CONTENTS = [
  "Profilo, impostazioni, consensi ed esito della verifica dell'età",
  "I tuoi fit con capi, prezzi, link e le foto",
  "Stili, capsule, chi segui e chi ti segue, account bloccati",
  "I voti che hai dato (per gli altri restano anonimi)",
  "Segnalazioni, decisioni di moderazione e reclami",
  "Notifiche, dispositivi e azioni registrate per gli Insight",
];

/** Scarica i tuoi dati (GDPR): archivio ZIP pronto in pochi minuti, valido 7 giorni. */
export default function DataExportScreen() {
  const latest = useExport();
  const request = useRequestExport();
  const data = latest.data;
  const tooSoon = request.error instanceof ApiError && request.error.code === "export.too_soon";

  let status;
  if (latest.isPending) status = <Loading label="Controllo l'archivio" />;
  else if (latest.isError) status = <ErrorNotice error={latest.error} onRetry={() => void latest.refetch()} />;
  else if (data?.status === "pending")
    status = (
      <View style={styles.card} role="status">
        <ActivityIndicator color={colors.accent} />
        <Text style={styles.cardTitle}>Stiamo preparando il tuo archivio</Text>
        <Text style={styles.text}>Di solito bastano pochi minuti. Ti mandiamo una notifica quando è pronto.</Text>
      </View>
    );
  else if (data?.status === "ready" && data.url)
    status = (
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Archivio pronto</Text>
        <Text style={styles.text}>
          {data.size_bytes ? `${formatBytes(data.size_bytes)} · ` : ""}scaricabile fino al{" "}
          {data.expires_at ? longDate(data.expires_at) : ""}
        </Text>
        <Button label="Scarica l'archivio" fullWidth onPress={() => void WebBrowser.openBrowserAsync(data.url!)} />
      </View>
    );
  else
    status = (
      <View style={styles.card}>
        {data?.status === "failed" ? (
          <Text style={[styles.text, styles.danger]}>L&apos;ultimo archivio non è riuscito. Riprova.</Text>
        ) : null}
        {data?.status === "expired" ? <Text style={styles.text}>L&apos;ultimo archivio è scaduto.</Text> : null}
        <Button
          label="Prepara l'archivio"
          fullWidth
          loading={request.isPending}
          onPress={() => request.mutate()}
        />
        {tooSoon ? <Text style={styles.text}>Puoi chiedere un nuovo archivio una volta al giorno.</Text> : null}
        {request.isError && !tooSoon ? (
          <Text style={[styles.text, styles.danger]} role="alert">
            Non è riuscito. Controlla la connessione e riprova.
          </Text>
        ) : null}
      </View>
    );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title="I tuoi dati" fallback="/settings" />
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.lead}>
          Ricevi un file ZIP con tutto quello che WearX conserva su di te, in un formato leggibile e portabile.
        </Text>
        {status}
        <Text style={styles.kicker}>COSA CONTIENE</Text>
        {CONTENTS.map((line) => (
          <Text key={line} style={styles.item}>
            — {line}
          </Text>
        ))}
        <Text style={styles.note}>
          L&apos;archivio resta scaricabile 7 giorni, poi lo cancelliamo. Il link per scaricarlo vale un&apos;ora: se
          scade, riapri questa pagina. Contiene dati personali: non condividerlo.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], gap: spacing[3], paddingBottom: spacing[8] },
  lead: { fontFamily: fonts.ui, fontSize: 15, lineHeight: 22, color: colors.text },
  card: {
    gap: spacing[3],
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.surface,
    alignItems: "stretch",
  },
  cardTitle: { fontFamily: fonts.display, fontSize: 20, color: colors.text },
  text: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textSecondary },
  danger: { color: colors.danger },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5, color: colors.textTertiary, marginTop: spacing[2] },
  item: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 21, color: colors.textMuted },
  note: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 18, color: colors.textSecondary, marginTop: spacing[2] },
});
