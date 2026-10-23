import { colors, spacing } from "@wearx/design-tokens";
import { ScrollView, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { PeopleSearch } from "@/features/people/PeopleSearch";
import { TopBar } from "@/ui/TopBar";

/**
 * Trova persone (dal profilo): la stessa ricerca di Esplora → Persone, con la tastiera già
 * aperta. Prima era solo il nickname esatto; dalla seduta 31 c'è la ricerca con i suggerimenti.
 */
export default function FindScreen() {
  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title="Trova persone" fallback="/profile" />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <PeopleSearch autoFocus />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], paddingBottom: spacing[6], maxWidth: 560, width: "100%", alignSelf: "center" },
});
