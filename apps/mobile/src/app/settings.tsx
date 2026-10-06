import { colors, fonts, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { LEGAL_TITLES, openLegal, useLegalLinks } from "@/features/legal/legal";
import { useUpdateProfile } from "@/features/privacy/api";
import { APP_VERSION } from "@/lib/api";
import { ListRow } from "@/ui/ListRow";
import { Toggle } from "@/ui/Toggle";
import { TopBar } from "@/ui/TopBar";
import { useToast } from "@/ui/Toast";

/** Privacy e sicurezza (prototipo, schermata Privacy). */
export default function SettingsScreen() {
  const { profile, signOut } = useAuth();
  const toast = useToast();
  const legal = useLegalLinks();
  const update = useUpdateProfile({ onError: () => toast.show("Modifica non salvata. Riprova.", { tone: "error" }) });

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title="Privacy e sicurezza" />
      <ScrollView contentContainerStyle={styles.content}>
        <Section title="I TUOI FIT">
          <Toggle
            label="Nascondi i prezzi"
            description="Gli altri vedono marca e capo, ma non quanto costa."
            value={profile?.hide_prices ?? false}
            onValueChange={(next) => update.mutate({ hide_prices: next })}
          />
          <Toggle
            label="Nascondi il numero dei voti"
            description="Gli altri vedono la media, non quante persone hanno votato."
            value={profile?.hide_vote_count ?? false}
            onValueChange={(next) => update.mutate({ hide_vote_count: next })}
          />
        </Section>

        {profile?.age_band === "18_plus" ? (
          <Section title="ACCOUNT">
            <ListRow
              label="Tipo di account"
              value={profile.account_type === "business" ? "Business" : "Privato"}
              onPress={() => router.push("/account-type")}
            />
            {profile.account_type === "business" ? (
              <ListRow
                label="I tuoi negozi"
                description="Verifica il sito del tuo negozio."
                onPress={() => router.push("/shop-domains")}
              />
            ) : null}
          </Section>
        ) : null}

        <Section title="ACCESSO">
          <ListRow label="Cambia password" onPress={() => router.push("/change-password")} />
          <ListRow
            label="Dispositivi collegati"
            description="Dove hai fatto l'accesso. Puoi uscire da quelli che non riconosci."
            onPress={() => router.push("/devices")}
          />
          <ListRow label="Notifiche" onPress={() => router.push("/notification-settings")} />
        </Section>

        <Section title="I TUOI DATI">
          <ListRow
            label="Scarica i tuoi dati"
            description="Un archivio con profilo, fit, foto, voti dati e tutto il resto."
            onPress={() => router.push("/data-export")}
          />
          <ListRow
            label="Cancella l'account"
            description="Hai 30 giorni per ripensarci."
            tone="danger"
            onPress={() => router.push("/delete-account")}
          />
        </Section>

        <Section title="AIUTO">
          <ListRow
            label="Segnala un problema"
            description="Qualcosa non va o hai un'idea? Arriva direttamente al team."
            onPress={() => router.push({ pathname: "/feedback", params: { from: "/settings" } })}
          />
        </Section>

        <Section title="INFORMAZIONI">
          {(["feed_explainer", "community_rules", "terms", "privacy"] as const).map((doc) => (
            <ListRow key={doc} label={LEGAL_TITLES[doc]} onPress={() => openLegal(legal[doc])} />
          ))}
        </Section>

        <ListRow label="Esci" onPress={() => void signOut()} />
        <Text style={styles.footer}>
          @{profile?.nickname} · WearX {APP_VERSION}
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text style={styles.kicker}>{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], gap: spacing[6], paddingBottom: spacing[8] },
  section: { gap: spacing[1] },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5, color: colors.textTertiary, marginBottom: 4 },
  footer: { fontFamily: fonts.mono, fontSize: 11, color: colors.textTertiary, textAlign: "center" },
});
