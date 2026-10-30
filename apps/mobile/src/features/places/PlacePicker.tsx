import type { PlaceSuggestion } from "@wearx/api-types";
import { colors, fonts, spacing } from "@wearx/design-tokens";
import { useEffect, useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { normalizePlaceQuery, PLACE_DEBOUNCE_MS, PLACE_QUERY_MAX, PLACE_QUERY_MIN, usePlaceSearch } from "@/features/places/api";
import { t } from "@/lib/i18n";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { Button } from "@/ui/Button";
import { IconPin } from "@/ui/icons";
import { SearchField } from "@/ui/SearchField";
import { Sheet } from "@/ui/Sheet";

type Props = {
  visible: boolean;
  /** Il luogo scelto ora (per mostrare "Togli il luogo"). */
  current: { name: string } | null;
  busy?: boolean;
  onClose: () => void;
  onPick: (place: PlaceSuggestion | null) => void;
};

/** Cerca il luogo del fit per nome, come su Mappe. Facoltativo. */
export function PlacePicker({ visible, current, busy = false, onClose, onPick }: Props) {
  const { profile } = useAuth();
  const minor = profile?.age_band === "16_17";
  const [text, setText] = useState("");
  const query = useDebouncedValue(normalizePlaceQuery(text), PLACE_DEBOUNCE_MS);
  const search = usePlaceSearch(visible ? query : "");
  useEffect(() => {
    if (!visible) setText("");
  }, [visible]);

  const items = query.length >= PLACE_QUERY_MIN ? (search.data?.items ?? []) : [];
  let status: string | null = null;
  if (query.length < PLACE_QUERY_MIN) {
    status = minor
      ? t("Scrivi il nome della città. Chi ha 16-17 anni può indicare solo la città.")
      : t("Scrivi il nome di un locale, una via o una città.")
  } else if (search.isError) status = t("Ricerca non disponibile ora. Riprova tra poco.");
  else if (!search.isFetching && search.data && items.length === 0) status = t("Nessun luogo con questo nome.");

  return (
    <Sheet visible={visible} title={t("Dove l'hai indossato?")} onClose={onClose}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <SearchField
          value={text}
          onChangeText={setText}
          label={t("Cerca il luogo")}
          placeholder={minor ? t("Cerca la città") : t("Cerca: un locale, una via, una città…")}
          maxLength={PLACE_QUERY_MAX}
          autoFocus
        />
        <View style={styles.statusRow} aria-live="polite">
          {search.isFetching && query.length >= PLACE_QUERY_MIN ? <ActivityIndicator color={colors.textSecondary} size="small" /> : null}
          {status ? <Text style={styles.status}>{status}</Text> : null}
        </View>
        <ScrollView style={styles.list} keyboardShouldPersistTaps="handled">
          {items.map((place) => (
            <Pressable
              key={place.ref}
              role="button"
              aria-label={place.detail ? `${place.name}, ${place.detail}` : place.name}
              disabled={busy}
              onPress={() => onPick(place)}
              style={({ pressed }) => [styles.row, pressed ? styles.pressed : null]}
            >
              <IconPin color={colors.textSecondary} size={18} />
              <View style={styles.rowText}>
                <Text style={styles.name} numberOfLines={1}>
                  {place.name}
                </Text>
                {place.detail ? (
                  <Text style={styles.detail} numberOfLines={1}>
                    {place.detail}
                  </Text>
                ) : null}
              </View>
            </Pressable>
          ))}
        </ScrollView>
        <Text style={styles.note}>
          {t("Lo vede chi vede il tuo profilo. Non usiamo la posizione del telefono e non si possono scegliere indirizzi di case.")}
        </Text>
        {current ? (
          <Button label={t("Togli il luogo")} variant="ghost" size="md" fullWidth loading={busy} onPress={() => onPick(null)} />
        ) : null}
      </KeyboardAvoidingView>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  statusRow: { flexDirection: "row", alignItems: "center", gap: spacing[2], minHeight: 28, marginTop: spacing[2] },
  status: { flex: 1, fontFamily: fonts.ui, fontSize: 13, lineHeight: 18, color: colors.textSecondary },
  list: { maxHeight: 290 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    minHeight: 56,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  pressed: { opacity: 0.6 },
  rowText: { flex: 1, minWidth: 0 },
  name: { fontFamily: fonts.uiSemiBold, fontSize: 15, color: colors.text },
  detail: { fontFamily: fonts.ui, fontSize: 13, color: colors.textSecondary, marginTop: 2 },
  note: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 17, color: colors.textTertiary, marginVertical: spacing[3] },
});
