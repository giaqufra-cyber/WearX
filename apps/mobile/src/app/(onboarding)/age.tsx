import { spacing } from "@wearx/design-tokens";
import { StyleSheet, View } from "react-native";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { useAuth } from "@/features/auth/AuthProvider";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/**
 * Passo 2 di 4: verifica dell'età. Per ora segnaposto: i metodi (selfie, SPID/CIE, documento)
 * e il collegamento al fornitore arrivano nella seduta 5.
 */
export default function AgeScreen() {
  const { signOut } = useAuth();
  return (
    <Screen>
      <AuthHeader step="PASSO 2 DI 4" onBack={() => void signOut()} />
      <Text variant="display" role="heading">
        Confermiamo{"\n"}che hai 16+
      </Text>
      <Text variant="secondary">
        Account confermato. Il prossimo passo è la verifica dell'età: la stiamo collegando e arriva con il prossimo
        aggiornamento.
      </Text>
      <View style={styles.actions}>
        <Button label="Esci" variant="secondary" onPress={() => void signOut()} fullWidth />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({ actions: { marginTop: spacing[6] } });
