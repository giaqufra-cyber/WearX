import { spacing } from "@wearx/design-tokens";
import { useRef } from "react";
import { StyleSheet, type TextInput, View } from "react-native";

import { TextField } from "@/ui/TextField";
import { t } from "@/lib/i18n";

export type BirthValue = { day: string; month: string; year: string };

const digits = (value: string) => value.replace(/\D/g, "");

/** Giorno / mese / anno affiancati; il cursore passa da solo al campo successivo. */
export function BirthDateFields({
  value,
  onChange,
}: {
  value: BirthValue;
  onChange: (patch: Partial<BirthValue>) => void;
}) {
  const monthRef = useRef<TextInput>(null);
  const yearRef = useRef<TextInput>(null);
  return (
    <View style={styles.row}>
      <View style={styles.small}>
        <TextField
          label={t("GIORNO")}
          value={value.day}
          onChangeText={(raw) => {
            onChange({ day: digits(raw) });
            if (digits(raw).length === 2) monthRef.current?.focus();
          }}
          placeholder={t("GG")}
          keyboardType="number-pad"
          maxLength={2}
          autoComplete="birthdate-day"
          centered
        />
      </View>
      <View style={styles.small}>
        <TextField
          ref={monthRef}
          label={t("MESE")}
          value={value.month}
          onChangeText={(raw) => {
            onChange({ month: digits(raw) });
            if (digits(raw).length === 2) yearRef.current?.focus();
          }}
          placeholder={t("MM")}
          keyboardType="number-pad"
          maxLength={2}
          autoComplete="birthdate-month"
          centered
        />
      </View>
      <View style={styles.year}>
        <TextField
          ref={yearRef}
          label={t("ANNO")}
          value={value.year}
          onChangeText={(raw) => onChange({ year: digits(raw) })}
          placeholder={t("AAAA")}
          keyboardType="number-pad"
          maxLength={4}
          autoComplete="birthdate-year"
          centered
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: spacing[2] },
  small: { flex: 1 },
  year: { flex: 1.6 },
});
