import { colors, fonts, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";

import { IconBack } from "@/ui/icons";
import { IconButton } from "@/ui/IconButton";

/** Barra in alto dei passi di registrazione: indietro a sinistra, "PASSO N DI 4" a destra. */
export function AuthHeader({ step, onBack }: { step?: string; onBack?: () => void }) {
  const back = onBack ?? (() => (router.canGoBack() ? router.back() : router.replace("/welcome")));
  return (
    <View style={styles.row}>
      <IconButton label="Indietro" onPress={back}>
        <IconBack color={colors.text} size={22} />
      </IconButton>
      {step ? <Text style={styles.step}>{step}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginHorizontal: -spacing[3],
    paddingTop: spacing[2],
  },
  step: {
    fontFamily: fonts.mono,
    fontSize: 11,
    letterSpacing: 11 * 0.14,
    color: colors.textSecondary,
    paddingRight: spacing[3],
  },
});
