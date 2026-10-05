import { colors, fonts, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { NoticeList } from "@/features/moderation/NoticeList";
import { IconButton } from "@/ui/IconButton";
import { IconBack } from "@/ui/icons";

/** Avvisi della moderazione: decisioni che ti riguardano, motivazioni, reclami. */
export default function ModerationScreen() {
  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <IconButton label="Indietro" onPress={() => (router.canGoBack() ? router.back() : router.replace("/profile"))}>
          <IconBack color={colors.text} />
        </IconButton>
        <Text style={styles.title} role="heading">
          Avvisi della moderazione
        </Text>
        <View style={styles.spacer} />
      </View>
      <ScrollView contentContainerStyle={styles.body}>
        <NoticeList />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: { flexDirection: "row", alignItems: "center", paddingHorizontal: 4, minHeight: 52 },
  title: { flex: 1, textAlign: "center", fontFamily: fonts.display, fontSize: 20, color: colors.text },
  spacer: { width: 44 },
  body: { padding: spacing[4], paddingBottom: spacing[8] },
});
