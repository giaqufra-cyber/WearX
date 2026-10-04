import { StyleSheet, View } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { EmptyState } from "@/ui/EmptyState";
import { Screen } from "@/ui/Screen";

/** Account sospeso dalla moderazione (seduta 16 per ricorsi e dettagli). */
export default function SuspendedScreen() {
  const { signOut } = useAuth();
  return (
    <Screen scroll={false}>
      <View style={styles.center}>
        <EmptyState
          title="Account sospeso"
          body="Abbiamo sospeso il tuo account per una violazione delle regole della community. Ti abbiamo scritto con i dettagli e come chiedere una revisione."
          action={{ label: "Esci", onPress: () => void signOut() }}
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({ center: { flex: 1, justifyContent: "center" } });
