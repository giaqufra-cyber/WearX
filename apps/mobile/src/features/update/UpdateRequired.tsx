import { colors, fonts, spacing } from "@wearx/design-tokens";
import { Linking, Platform, StyleSheet, Text, View } from "react-native";

import { useAppConfig } from "@/features/styles/useAppConfig";
import { APP_VERSION } from "@/lib/api";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";

/** Versione troppo vecchia: l'unica cosa da fare è aggiornare dallo store. */
export function UpdateRequired() {
  const config = useAppConfig();
  const store =
    Platform.OS === "ios" ? config.data?.store.ios : Platform.OS === "android" ? config.data?.store.android : null;
  const minimum = config.data?.min_app_version;

  return (
    <Screen scroll={false}>
      <View style={styles.body}>
        <Text style={styles.kicker}>NUOVA VERSIONE</Text>
        <Text style={styles.title} role="heading">
          Aggiorna WearX
        </Text>
        <Text style={styles.text}>
          Questa versione dell&apos;app non è più supportata: aggiornala per continuare a votare e pubblicare. I tuoi
          fit, i voti e le impostazioni restano come sono.
        </Text>
        <Text style={styles.version}>
          {minimum ? `Hai la ${APP_VERSION} · serve almeno la ${minimum}` : `Hai la ${APP_VERSION}`}
        </Text>
      </View>
      <View style={styles.actions}>
        {store ? (
          <Button
            label={Platform.OS === "ios" ? "Apri l'App Store" : "Apri Google Play"}
            fullWidth
            onPress={() => void Linking.openURL(store)}
          />
        ) : (
          <Text style={styles.text}>Cerca «WearX» nello store del tuo telefono.</Text>
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: { flex: 1, justifyContent: "center", gap: spacing[3] },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.5, color: colors.accent },
  title: { fontFamily: fonts.display, fontSize: 38, color: colors.text },
  text: { fontFamily: fonts.ui, fontSize: 15, lineHeight: 22, color: colors.textSecondary },
  version: { fontFamily: fonts.mono, fontSize: 12, color: colors.textMuted, marginTop: spacing[2] },
  actions: { gap: spacing[2], paddingBottom: spacing[4] },
});
