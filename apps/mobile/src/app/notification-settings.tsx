import type { NotificationSettings } from "@wearx/api-types";
import { colors, fonts, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useNotificationSettings, useUpdateNotificationSettings } from "@/features/notifications/api";
import { PushPrompt, usePushStatus } from "@/features/notifications/PushPrompt";
import { IconButton } from "@/ui/IconButton";
import { IconBack } from "@/ui/icons";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { Toggle } from "@/ui/Toggle";
import { useToast } from "@/ui/Toast";

const ROWS: { key: keyof NotificationSettings; label: string; description: string }[] = [
  { key: "follows", label: "Follow", description: "Richieste, nuovi follower, richieste accettate." },
  { key: "votes", label: "Voti ai tuoi fit", description: "Quando un fit raggiunge 10, 25, 50, 100… voti. Mai voto per voto." },
  {
    key: "moderation",
    label: "Moderazione",
    description: "Decisioni sui tuoi contenuti ed esito dei reclami. Sul telefono il testo resta generico.",
  },
];

/** Quali notifiche arrivano sul telefono. La lista nell'app resta sempre completa. */
export default function NotificationSettingsScreen() {
  const settings = useNotificationSettings();
  const toast = useToast();
  const update = useUpdateNotificationSettings({
    onError: () => toast.show("Modifica non salvata. Riprova.", { tone: "error" }),
  });
  const push = usePushStatus();

  let body;
  if (settings.isPending) body = <Loading label="Carico le impostazioni" />;
  else if (settings.isError) body = <ErrorNotice error={settings.error} onRetry={() => void settings.refetch()} />;
  else
    body = (
      <View style={styles.group}>
        {ROWS.map((row) => (
          <Toggle
            key={row.key}
            label={row.label}
            description={row.description}
            value={settings.data[row.key]}
            onValueChange={(next) => update.mutate({ [row.key]: next })}
          />
        ))}
      </View>
    );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <IconButton label="Indietro" onPress={() => (router.canGoBack() ? router.back() : router.replace("/notifications"))}>
          <IconBack color={colors.text} />
        </IconButton>
        <Text style={styles.title} role="heading">
          Notifiche
        </Text>
        <View style={styles.spacer} />
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.kicker}>SUL TELEFONO</Text>
        <PushPrompt compact />
        {push.data === "unsupported" ? (
          <Text style={styles.note}>Su questo dispositivo le notifiche si vedono solo dentro l&apos;app.</Text>
        ) : null}
        {body}
        <Text style={styles.note}>
          I ragazzi e le ragazze di 16-17 anni non ricevono notifiche sul telefono tra le 22 e le 7: arrivano al mattino.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 4, minHeight: 52 },
  title: { flex: 1, textAlign: "center", fontFamily: fonts.display, fontSize: 20, color: colors.text },
  spacer: { width: 44 },
  content: { padding: spacing[4], gap: spacing[3], paddingBottom: spacing[8] },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5, color: colors.textTertiary },
  group: { gap: spacing[1] },
  note: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textSecondary },
});
