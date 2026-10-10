import { colors, fonts, fontSizes, radii, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, type TextInputProps, View } from "react-native";

import type { DraftPhoto } from "@/features/create/draft";
import { BRAND_MAX, type ItemDraft, itemErrors, NAME_MAX } from "@/features/create/form";
import { PinSheet } from "@/features/create/PinSheet";
import { IconTag } from "@/ui/icons";

type Props = {
  index: number;
  item: ItemDraft;
  /** Le foto del fit, per segnare dove si vede il capo. */
  photos: Pick<DraftPhoto, "localId" | "uri" | "width" | "height">[];
  canRemove: boolean;
  onChange: (patch: Partial<ItemDraft>) => void;
  onRemove: () => void;
};

function Field({ error, ...props }: TextInputProps & { error?: string }) {
  return (
    <TextInput
      {...props}
      aria-invalid={Boolean(error)}
      placeholderTextColor={colors.textTertiary}
      selectionColor={colors.accent}
      style={[styles.input, error ? styles.inputError : null]}
    />
  );
}

/** Un capo del fit (prototipo, "3 · I CAPI"): brand, capo, prezzo, link al negozio. */
export function ItemCard({ index, item, photos, canRemove, onChange, onRemove }: Props) {
  const [pinning, setPinning] = useState(false);
  const errors = itemErrors(item);
  const pinPhoto = item.pin ? photos.findIndex((p) => p.localId === item.pin!.photo) : -1;
  const label = [item.brand.trim(), item.name.trim()].filter(Boolean).join(" ") || `capo ${index + 1}`;
  const messages = [errors.brand, errors.name, errors.price, errors.link].filter(Boolean);
  return (
    <View style={styles.card}>
      <View style={styles.head}>
        <Text style={styles.title}>Capo {index + 1}</Text>
        {canRemove ? (
          <Pressable role="button" aria-label={`Rimuovi il capo ${index + 1}`} onPress={onRemove} hitSlop={8}>
            <Text style={styles.remove}>Rimuovi</Text>
          </Pressable>
        ) : null}
      </View>
      <View style={styles.grid}>
        <View style={styles.cell}>
          <Field
            aria-label={`Brand del capo ${index + 1}`}
            placeholder="Brand"
            value={item.brand}
            onChangeText={(brand) => onChange({ brand })}
            maxLength={BRAND_MAX}
            autoCorrect={false}
            error={errors.brand}
          />
        </View>
        <View style={styles.cell}>
          <Field
            aria-label={`Nome del capo ${index + 1}`}
            placeholder="Capo (es. blazer)"
            value={item.name}
            onChangeText={(name) => onChange({ name })}
            maxLength={NAME_MAX}
            error={errors.name}
          />
        </View>
      </View>
      <View style={styles.grid}>
        <View style={styles.cell}>
          <Field
            aria-label={`Prezzo in euro del capo ${index + 1}`}
            placeholder="Prezzo € (opz.)"
            value={item.price}
            onChangeText={(price) => onChange({ price })}
            keyboardType="decimal-pad"
            maxLength={12}
            error={errors.price}
          />
        </View>
        <View style={styles.cell}>
          <Field
            aria-label={`Link del negozio del capo ${index + 1}`}
            placeholder="Link shop (opz.)"
            value={item.link}
            onChangeText={(link) => onChange({ link })}
            keyboardType="url"
            autoCapitalize="none"
            autoCorrect={false}
            error={errors.link}
          />
        </View>
      </View>
      {photos.length ? (
        <Pressable
          role="button"
          aria-label={
            pinPhoto >= 0
              ? `Capo ${index + 1} segnato sulla foto ${pinPhoto + 1}: cambia il punto`
              : `Segna il capo ${index + 1} sulla foto`
          }
          onPress={() => setPinning(true)}
          style={({ pressed }) => [styles.pin, pinPhoto >= 0 ? styles.pinSet : null, pressed ? styles.pressed : null]}
        >
          <IconTag color={pinPhoto >= 0 ? colors.text : colors.textSecondary} />
          <Text style={[styles.pinText, pinPhoto >= 0 ? styles.pinTextSet : null]}>
            {pinPhoto >= 0 ? `Sulla foto ${pinPhoto + 1} · Cambia` : "Segna sulla foto (opz.)"}
          </Text>
        </Pressable>
      ) : null}
      <PinSheet
        visible={pinning}
        itemLabel={label}
        photos={photos}
        pin={pinPhoto >= 0 ? item.pin : null}
        onSave={(pin) => onChange({ pin })}
        onClose={() => setPinning(false)}
      />
      {messages.length ? (
        <Text style={styles.error} role="alert">
          {messages.join(" ")}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    borderRadius: 16,
    padding: spacing[3],
    backgroundColor: "#111113",
    gap: spacing[2],
  },
  head: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", minHeight: 28 },
  title: { fontFamily: fonts.uiBold, fontSize: 12, color: colors.textSecondary },
  remove: { fontFamily: fonts.ui, fontSize: 12, color: colors.textSecondary },
  grid: { flexDirection: "row", gap: spacing[2] },
  cell: { flex: 1, minWidth: 0 },
  input: {
    height: 44,
    minWidth: 0,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceRaised,
    color: colors.text,
    paddingHorizontal: 12,
    fontFamily: fonts.ui,
    fontSize: fontSizes.body,
    outlineWidth: 0,
  },
  inputError: { borderColor: colors.dangerStrong },
  pin: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing[2],
    minHeight: 40,
    paddingHorizontal: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderStyle: "dashed",
    borderColor: colors.border,
  },
  pinSet: { borderStyle: "solid", borderColor: colors.textSecondary },
  pinText: { fontFamily: fonts.ui, fontSize: 13, color: colors.textSecondary },
  pinTextSet: { fontFamily: fonts.uiBold, color: colors.text },
  pressed: { opacity: 0.7 },
  error: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 17, color: colors.danger },
});
