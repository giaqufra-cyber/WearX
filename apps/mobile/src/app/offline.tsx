import { spacing } from "@wearx/design-tokens";
import { Platform, StyleSheet, View } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { changeDemoServer } from "@/features/demo/demoStore";
import { env } from "@/lib/env";
import { Button } from "@/ui/Button";
import { EmptyState } from "@/ui/EmptyState";
import { Screen } from "@/ui/Screen";

/** Sessione valida ma API non raggiungibile: si riprova, oppure si esce. */
export default function OfflineScreen() {
  const { retry, signOut } = useAuth();
  return (
    <Screen scroll={false}>
      <View style={styles.center}>
        <EmptyState
          title="Non riusciamo a raggiungere WearX"
          body="Controlla la connessione. I tuoi dati sono al sicuro: riprova tra poco."
          action={{ label: "Riprova", onPress: retry }}
        />
        {env.demo && Platform.OS !== "web" ? (
          <Button label="Cambia server della demo" variant="secondary" size="md" onPress={changeDemoServer} fullWidth />
        ) : null}
        <Button label="Esci dall'account" variant="ghost" size="md" onPress={() => void signOut()} fullWidth />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({ center: { flex: 1, justifyContent: "center", gap: spacing[2] } });
