import { colors, fonts, spacing } from "@wearx/design-tokens";
import { ScrollView, StyleSheet, Text } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { NoticeList } from "@/features/moderation/NoticeList";
import { Button } from "@/ui/Button";

/** Account sospeso o chiuso dalla moderazione: il motivo e il reclamo, senza entrare nell'app. */
export default function SuspendedScreen() {
  const { signOut } = useAuth();
  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <ScrollView contentContainerStyle={styles.body}>
        <Text style={styles.title} role="heading">
          Account sospeso
        </Text>
        <Text style={styles.text}>
          Qui sotto trovi la decisione, il motivo e come fare reclamo. Il reclamo lo legge un moderatore diverso da
          chi ha deciso.
        </Text>
        <NoticeList canOpenPosts={false} />
        <Button label="Esci" variant="secondary" size="md" onPress={() => void signOut()} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  body: { padding: spacing[5], gap: spacing[4] },
  title: { fontFamily: fonts.display, fontSize: 34, color: colors.text, marginTop: spacing[4] },
  text: { fontFamily: fonts.ui, fontSize: 15, lineHeight: 22, color: colors.textSecondary },
});
