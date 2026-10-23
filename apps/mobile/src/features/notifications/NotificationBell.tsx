import { colors, fonts } from "@wearx/design-tokens";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { useUnreadCount } from "@/features/notifications/api";
import { IconButton } from "@/ui/IconButton";
import { IconBell } from "@/ui/icons";
import { t, tn } from "@/lib/i18n";

/** Campanella con il numero delle notifiche non lette (oltre 99: "99+"). */
export function NotificationBell() {
  const unread = useUnreadCount();
  const count = unread.data ?? 0;
  const label = count > 0 ? tn(count, "Notifiche, {count} non letta", "Notifiche, {count} non lette") : t("Notifiche");
  return (
    <IconButton label={label} onPress={() => router.push("/notifications")}>
      <View>
        <IconBell color={colors.text} />
        {count > 0 ? (
          <View style={styles.badge} pointerEvents="none">
            <Text style={styles.count} maxFontSizeMultiplier={1.2}>
              {count > 99 ? "99+" : String(count)}
            </Text>
          </View>
        ) : null}
      </View>
    </IconButton>
  );
}

const styles = StyleSheet.create({
  badge: {
    position: "absolute",
    top: -5,
    right: -8,
    minWidth: 18,
    height: 18,
    paddingHorizontal: 4,
    borderRadius: 9,
    backgroundColor: colors.accent,
    borderWidth: 2,
    borderColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
  },
  count: { fontFamily: fonts.uiExtraBold, fontSize: 9, lineHeight: 11, color: colors.onAccent },
});
