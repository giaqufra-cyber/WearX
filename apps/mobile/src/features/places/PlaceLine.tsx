import type { FitPlace } from "@wearx/api-types";
import { colors, fonts } from "@wearx/design-tokens";
import * as WebBrowser from "expo-web-browser";
import { Linking, Platform, Pressable, StyleSheet, Text } from "react-native";

import { mapsUrl, placeLabel } from "@/features/places/api";
import { t } from "@/lib/i18n";
import { IconPin } from "@/ui/icons";

/** Il luogo di un fit, sotto lo stile: un tocco lo apre in Mappe. */
export function PlaceLine({ place }: { place: FitPlace }) {
  const open = () => {
    const url = mapsUrl(place);
    if (Platform.OS === "web") void WebBrowser.openBrowserAsync(url);
    else void Linking.openURL(url).catch(() => undefined);
  };
  return (
    <Pressable
      role="link"
      aria-label={t("Luogo: {place}. Apri in Mappe", { place: placeLabel(place) })}
      onPress={open}
      hitSlop={6}
      style={({ pressed }) => [styles.row, pressed ? styles.pressed : null]}
    >
      <IconPin color={colors.textSecondary} size={13} />
      <Text style={styles.text} numberOfLines={1}>
        <Text style={styles.name}>{place.name}</Text>
        {place.detail ? ` · ${place.detail}` : ""}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: 4, marginTop: 2, alignSelf: "flex-start", maxWidth: "100%" },
  pressed: { opacity: 0.6 },
  text: { flexShrink: 1, fontFamily: fonts.ui, fontSize: 12, color: colors.textSecondary },
  name: { fontFamily: fonts.uiSemiBold, color: colors.text },
});
