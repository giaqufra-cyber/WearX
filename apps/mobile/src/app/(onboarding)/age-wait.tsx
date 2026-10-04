import { spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";

import { useAgeStatus } from "@/features/onboarding/api";
import { Button } from "@/ui/Button";
import { Loading } from "@/ui/LoadState";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

const SLOW_AFTER_MS = 90_000;

/** In attesa dell'esito dal fornitore (arriva con il webhook, di solito in pochi secondi). */
export default function AgeWaitScreen() {
  const status = useAgeStatus({ poll: true });
  const [slow, setSlow] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => clearTimeout(timer);
  }, []);

  // Si guarda solo l'esito letto dopo l'apertura: quello in cache è del tentativo precedente.
  const data = status.isFetchedAfterMount ? status.data : undefined;
  useEffect(() => {
    if (!data) return;
    if (data.verified) router.replace("/profile-type");
    else if (data.latest?.status !== "pending") router.replace("/age");
  }, [data]);

  return (
    <Screen scroll={false}>
      <View style={styles.center}>
        <Loading label="Aspettiamo l'esito della verifica…" />
        {slow ? (
          <Text variant="secondary" style={styles.text}>
            Ci sta mettendo più del solito. Puoi aspettare o tornare ai metodi di verifica.
          </Text>
        ) : null}
        <Button label="Torna ai metodi" variant="ghost" size="md" onPress={() => router.replace("/age")} fullWidth />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, justifyContent: "center", gap: spacing[3] },
  text: { textAlign: "center" },
});
