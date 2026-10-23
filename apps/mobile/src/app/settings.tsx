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
import { t } from "@/lib/i18n";

/** Privacy e sicurezza (prototipo, schermata Privacy). */
export default function SettingsScreen() {
  const { profile, signOut } = useAuth();
  const toast = useToast();
  const legal = useLegalLinks();
  const update = useUpdateProfile({ onError: () => toast.show(t("Modifica non salvata. Riprova."), { tone: "error" }) });

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title={t("Privacy e sicurezza")} />
      <ScrollView contentContainerStyle={styles.content}>
        <Section title={t("I TUOI FIT")}>
          <Toggle
            label={t("Nascondi i prezzi")}
            description={t("Gli altri vedono marca e capo, ma non quanto costa.")}
            value={profile?.hide_prices ?? false}
            onValueChange={(next) => update.mutate({ hide_prices: next })}
          />
          <Toggle
            label={t("Nascondi il numero dei voti")}
            description={t("Gli altri vedono la media, non quante persone hanno votato.")}
            value={profile?.hide_vote_count ?? false}
            onValueChange={(next) => update.mutate({ hide_vote_count: next })}
          />
        </Section>

        <Section title={t("RICERCA")}>
          <Toggle
            label={t("Fatti trovare nella ricerca")}
            description={
              profile?.age_band === "16_17"
                ? t("Ti trovano solo altri utenti tra 16 e 17 anni. Spento: ti trova solo chi scrive il tuo nickname esatto.")
                : t("Spento: ti trova solo chi scrive il tuo nickname esatto o chi ti conosce già, e non compari nei suggerimenti.")
            }
            value={profile?.discoverable ?? false}
            onValueChange={(next) => update.mutate({ discoverable: next })}
          />
        </Section>

        {profile?.age_band === "18_plus" ? (
          <Section title={t("ACCOUNT")}>
            <ListRow
              label={t("Tipo di account")}
              value={profile.account_type === "business" ? "Business" : "Privato"}
              onPress={() => router.push("/account-type")}
            />
            {profile.account_type === "business" ? (
              <ListRow
                label={t("I tuoi negozi")}
                description={t("Verifica il sito del tuo negozio.")}
                onPress={() => router.push("/shop-domains")}
              />
            ) : null}
          </Section>
        ) : null}

        <Section title={t("ACCESSO")}>
          <ListRow label={t("Cambia password")} onPress={() => router.push("/change-password")} />
          <ListRow
            label={t("Dispositivi collegati")}
            description={t("Dove hai fatto l'accesso. Puoi uscire da quelli che non riconosci.")}
            onPress={() => router.push("/devices")}
          />
          <ListRow label={t("Notifiche")} onPress={() => router.push("/notification-settings")} />
        </Section>

        <Section title={t("I TUOI DATI")}>
          <ListRow
            label={t("Scarica i tuoi dati")}
            description={t("Un archivio con profilo, fit, foto, voti dati e tutto il resto.")}
            onPress={() => router.push("/data-export")}
          />
          <ListRow
            label={t("Cancella l'account")}
            description={t("Hai 30 giorni per ripensarci.")}
            tone="danger"
            onPress={() => router.push("/delete-account")}
          />
        </Section>

        <Section title={t("AIUTO")}>
          <ListRow
            label={t("Segnala un problema")}
            description={t("Qualcosa non va o hai un'idea? Arriva direttamente al team.")}
            onPress={() => router.push({ pathname: "/feedback", params: { from: "/settings" } })}
          />
        </Section>

        <Section title={t("INFORMAZIONI")}>
          {(["feed_explainer", "community_rules", "terms", "privacy"] as const).map((doc) => (
            <ListRow key={doc} label={LEGAL_TITLES[doc]} onPress={() => openLegal(legal[doc])} />
          ))}
        </Section>

        <ListRow label={t("Esci")} onPress={() => void signOut()} />
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
