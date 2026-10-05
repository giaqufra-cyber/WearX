import { colors, fonts } from "@wearx/design-tokens";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { NotificationList } from "@/features/notifications/NotificationList";
import { IconButton } from "@/ui/IconButton";
import { IconBack, IconSliders } from "@/ui/icons";

/** Notifiche: follow, traguardi dei fit, moderazione. */
export default function NotificationsScreen() {
  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <IconButton label="Indietro" onPress={() => (router.canGoBack() ? router.back() : router.replace("/"))}>
          <IconBack color={colors.text} />
        </IconButton>
        <Text style={styles.title} role="heading">
          Notifiche
        </Text>
        <IconButton label="Impostazioni delle notifiche" onPress={() => router.push("/notification-settings")}>
          <IconSliders color={colors.text} />
        </IconButton>
      </View>
      <NotificationList />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  header: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 4,
    minHeight: 52,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  title: { flex: 1, textAlign: "center", fontFamily: fonts.display, fontSize: 20, color: colors.text },
});
