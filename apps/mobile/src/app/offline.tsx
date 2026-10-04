import { spacing } from "@wearx/design-tokens";
import { StyleSheet, View } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
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
        <Button label="Esci dall'account" variant="ghost" size="md" onPress={() => void signOut()} fullWidth />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({ center: { flex: 1, justifyContent: "center", gap: spacing[2] } });
