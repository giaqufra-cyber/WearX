import { spacing } from "@wearx/design-tokens";
import { StyleSheet } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Profilo-portfolio. Griglia, riordino e capsule: seduta 14. */
export default function ProfileScreen() {
  const { profile, signOut } = useAuth();
  return (
    <Screen>
      <Text variant="display" role="heading" style={styles.title}>Il tuo portfolio</Text>
      {profile ? <Text variant="bodyStrong">@{profile.nickname}</Text> : null}
      <Text variant="secondary">I tuoi fit, nell'ordine che scegli tu.</Text>
      <Button label="Esci" variant="secondary" size="md" onPress={() => void signOut()} />
    </Screen>
  );
}

const styles = StyleSheet.create({ title: { paddingTop: spacing[3] } });
