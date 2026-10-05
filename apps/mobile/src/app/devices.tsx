import type { Device } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { signOutOtherDevices } from "@/features/auth/recovery";
import { lastSeen, useDevices, useRevokeDevice } from "@/features/privacy/api";
import { Button } from "@/ui/Button";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { Sheet } from "@/ui/Sheet";
import { TopBar } from "@/ui/TopBar";
import { useToast } from "@/ui/Toast";

const PLATFORM: Record<Device["platform"], string> = { ios: "iOS", android: "Android", web: "Web" };

/** Dove hai fatto l'accesso. Si esce da un dispositivo alla volta o da tutti gli altri. */
export default function DevicesScreen() {
  const devices = useDevices();
  const revoke = useRevokeDevice();
  const toast = useToast();
  const [confirm, setConfirm] = useState<Device | "others" | null>(null);
  const [busy, setBusy] = useState(false);
  const others = (devices.data ?? []).filter((d) => !d.current);

  const run = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      if (confirm === "others") await signOutOtherDevices();
      else await revoke.mutateAsync(confirm.id);
      toast.show(confirm === "others" ? "Sei uscito da tutti gli altri dispositivi." : `Uscito da ${confirm.label}.`);
      void devices.refetch();
    } catch {
      toast.show("Non è riuscito. Riprova.", { tone: "error" });
    } finally {
      setBusy(false);
      setConfirm(null);
    }
  };

  let body;
  if (devices.isPending) body = <Loading label="Carico i dispositivi" />;
  else if (devices.isError) body = <ErrorNotice error={devices.error} onRetry={() => void devices.refetch()} />;
  else
    body = (
      <>
        {devices.data.map((d) => (
          <View key={d.id} style={styles.device}>
            <View style={styles.deviceText}>
              <Text style={styles.label}>{d.label}</Text>
              <Text style={styles.meta}>
                {PLATFORM[d.platform]}
                {d.app_version ? ` · app ${d.app_version}` : ""} ·{" "}
                {d.current ? "questo dispositivo" : lastSeen(d.last_seen)}
              </Text>
            </View>
            {d.current ? (
              <Text style={styles.current}>QUI</Text>
            ) : (
              <Button label="Esci" size="sm" variant="secondary" onPress={() => setConfirm(d)} />
            )}
          </View>
        ))}
        {others.length > 0 ? (
          <Button label="Esci da tutti gli altri dispositivi" variant="secondary" fullWidth onPress={() => setConfirm("others")} />
        ) : null}
        <Text style={styles.note}>
          Se non riconosci un dispositivo, esci da lì e cambia la password. Dopo un cambio di password esci da solo da
          tutti gli altri.
        </Text>
      </>
    );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title="Dispositivi" fallback="/settings" />
      <ScrollView contentContainerStyle={styles.content}>{body}</ScrollView>
      <Sheet
        visible={confirm !== null}
        title={confirm === "others" ? "Uscire da tutti gli altri?" : `Uscire da ${confirm?.label ?? ""}?`}
        onClose={() => setConfirm(null)}
      >
        <Text style={styles.note}>Lì dovrai accedere di nuovo con email e password.</Text>
        <Button label="Esci" variant="danger" loading={busy} onPress={() => void run()} fullWidth />
        <Button label="Annulla" variant="ghost" onPress={() => setConfirm(null)} fullWidth />
      </Sheet>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], gap: spacing[3], paddingBottom: spacing[8] },
  device: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing[3],
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.surface,
  },
  deviceText: { flex: 1, gap: 3 },
  label: { fontFamily: fonts.uiSemiBold, fontSize: 15, color: colors.text },
  meta: { fontFamily: fonts.ui, fontSize: 13, color: colors.textSecondary },
  current: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5, color: colors.accent },
  note: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textSecondary },
});
