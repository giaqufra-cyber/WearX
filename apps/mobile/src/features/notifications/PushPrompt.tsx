import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Linking, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { NOTIFICATIONS_KEY } from "@/features/notifications/keys";
import { enablePush, pushStatus } from "@/features/notifications/push";
import { Button } from "@/ui/Button";
import { IconBell } from "@/ui/icons";
import { useToast } from "@/ui/Toast";

const STATUS_KEY = [...NOTIFICATIONS_KEY, "push-status"] as const;

/** Stato del permesso per i push su questo telefono. */
export function usePushStatus() {
  return useQuery({ queryKey: STATUS_KEY, queryFn: pushStatus, staleTime: 0 });
}

/**
 * Invito ad attivare i push: si chiede il permesso solo quando la persona tocca "Attiva".
 * Se l'ha negato, si spiega come riattivarlo dalle impostazioni del telefono.
 */
export function PushPrompt({ compact = false }: { compact?: boolean }) {
  const status = usePushStatus();
  const { session } = useAuth();
  const client = useQueryClient();
  const toast = useToast();

  if (status.data === "undetermined") {
    return (
      <View style={[styles.card, compact && styles.compact]}>
        <View style={styles.icon}>
          <IconBell color={colors.onAccent} size={20} />
        </View>
        <View style={styles.text}>
          <Text style={styles.title}>Attiva le notifiche sul telefono</Text>
          <Text style={styles.body}>
            Ti avvisiamo quando qualcuno ti segue, quando un tuo fit raggiunge nuovi voti e per gli avvisi della
            moderazione. Mai pubblicità.
          </Text>
          <View style={styles.action}>
            <Button
              label="Attiva"
              size="sm"
              onPress={async () => {
                try {
                  if (session) await enablePush(session.access_token, { ask: true });
                } catch {
                  toast.show("Non siamo riusciti ad attivare le notifiche. Riprova più tardi.", { tone: "error" });
                }
                void client.invalidateQueries({ queryKey: STATUS_KEY });
              }}
            />
          </View>
        </View>
      </View>
    );
  }
  if (status.data === "denied") {
    return (
      <View style={[styles.card, styles.muted, compact && styles.compact]}>
        <View style={styles.text}>
          <Text style={styles.title}>Notifiche spente sul telefono</Text>
          <Text style={styles.body}>Le trovi comunque qui. Per riceverle, attivale nelle impostazioni del telefono.</Text>
          <View style={styles.action}>
            <Button label="Apri impostazioni" size="sm" variant="secondary" onPress={() => void Linking.openSettings()} />
          </View>
        </View>
      </View>
    );
  }
  return null;
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    gap: spacing[3],
    margin: spacing[4],
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  compact: { marginHorizontal: 0 },
  muted: { backgroundColor: colors.background },
  icon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  text: { flex: 1, gap: 6 },
  title: { fontFamily: fonts.uiSemiBold, fontSize: 15, color: colors.text },
  body: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textSecondary },
  action: { flexDirection: "row", marginTop: spacing[1] },
});
