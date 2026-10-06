import { colors, fonts, fontSizes, radii, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { LegalLink } from "@/features/legal/legal";
import { Button } from "@/ui/Button";

/** Benvenuto (prototipo, schermata Splash). */
export default function WelcomeScreen() {
  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <View style={styles.top}>
        <Text style={styles.kicker}>FIT · CHECK · VOTE</Text>
        <View style={styles.badge} aria-label="Solo dai 16 anni in su">
          <Text style={styles.badgeText}>16+</Text>
        </View>
      </View>

      <View>
        <Text style={styles.serifSmall}>il tuo stile,</Text>
        <Text style={styles.logo} role="heading" aria-label="WearX">
          WEAR<Text style={{ color: colors.accent }}>X</Text>
        </Text>
        <Text style={styles.serifLarge}>votato da chi{"\n"}lo capisce.</Text>
        <Text style={styles.lead}>
          Posta i tuoi fit, entra negli stili che ti rappresentano e ricevi un voto da 1 a 100. Niente commenti.
          Solo stile.
        </Text>
      </View>

      <View style={styles.actions}>
        <Button label="Crea il tuo account" onPress={() => router.push("/signup")} fullWidth />
        <Button label="Ho già un account" variant="secondary" onPress={() => router.push("/login")} fullWidth />
        <Text style={styles.legal}>
          Continuando accetti i <LegalLink doc="terms" label="Termini" /> (come usiamo i dati:{" "}
          <LegalLink doc="privacy" label="Informativa privacy" />).{"\n"}WearX è riservata a chi ha almeno 16 anni.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.background,
    justifyContent: "space-between",
    paddingHorizontal: spacing[7],
    paddingTop: spacing[6],
    paddingBottom: spacing[6],
  },
  top: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 11 * 0.16, color: colors.textSecondary },
  badge: {
    borderWidth: 1,
    borderColor: colors.text,
    borderRadius: radii.pill,
    paddingVertical: 5,
    paddingHorizontal: 11,
  },
  badgeText: { fontFamily: fonts.uiExtraBold, fontSize: 11, letterSpacing: 11 * 0.08, color: colors.text },
  serifSmall: { fontFamily: fonts.display, fontSize: 30, lineHeight: 32, color: colors.textSecondary },
  logo: {
    fontFamily: fonts.numeric,
    fontSize: fontSizes.logo,
    lineHeight: fontSizes.logo * 0.92,
    letterSpacing: -fontSizes.logo * 0.045,
    color: colors.text,
    marginTop: spacing[3],
  },
  serifLarge: { fontFamily: fonts.display, fontSize: 32, lineHeight: 34, color: colors.text, marginTop: spacing[3] },
  lead: {
    fontFamily: fonts.ui,
    fontSize: fontSizes.bodyLarge,
    lineHeight: 22,
    color: colors.textSecondary,
    maxWidth: 310,
    marginTop: spacing[5],
  },
  actions: { gap: spacing[3] },
  legal: {
    fontFamily: fonts.ui,
    fontSize: 11,
    lineHeight: 16,
    color: colors.textTertiary,
    textAlign: "center",
    marginTop: spacing[1],
  },
});
