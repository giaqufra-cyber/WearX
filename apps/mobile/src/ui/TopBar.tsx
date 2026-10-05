import { colors, fonts } from "@wearx/design-tokens";
import { router } from "expo-router";
import type { ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";

import { IconButton } from "@/ui/IconButton";
import { IconBack } from "@/ui/icons";

type Props = { title: string; fallback?: string; right?: ReactNode };

/** Barra in alto delle schermate secondarie: indietro, titolo al centro, azione facoltativa. */
export function TopBar({ title, fallback = "/profile", right }: Props) {
  return (
    <View style={styles.bar}>
      <IconButton label="Indietro" onPress={() => (router.canGoBack() ? router.back() : router.replace(fallback as never))}>
        <IconBack color={colors.text} />
      </IconButton>
      <Text style={styles.title} role="heading" numberOfLines={1}>
        {title}
      </Text>
      {right ?? <View style={styles.spacer} />}
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: "row", alignItems: "center", paddingHorizontal: 4, minHeight: 52 },
  title: { flex: 1, textAlign: "center", fontFamily: fonts.display, fontSize: 20, color: colors.text },
  spacer: { width: 44 },
});
