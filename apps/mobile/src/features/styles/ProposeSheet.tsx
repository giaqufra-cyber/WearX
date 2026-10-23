import { colors, fonts, fontSizes, radii, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { CATEGORIES, type StyleCategory } from "@/features/styles/catalog";
import { existingStyle, proposalError, usePropose } from "@/features/styles/proposals";
import { Button } from "@/ui/Button";
import { Sheet } from "@/ui/Sheet";
import { useToast } from "@/ui/Toast";
import { t } from "@/lib/i18n";

const NAME_MAX = 30;
const TAGLINE_MAX = 60;

type Props = {
  visible: boolean;
  initialName?: string;
  onClose: () => void;
  /** Lo stile c'è già: di base si apre la sua pagina; in "Nuovo fit" invece lo si sceglie. */
  onExisting?: (slug: string) => void;
};

/** Proponi uno stile nuovo (seduta 30): nome, categoria, descrizione facoltativa. */
export function ProposeSheet({ visible, initialName = "", onClose, onExisting }: Props) {
  const [name, setName] = useState(initialName);
  const [tagline, setTagline] = useState("");
  const [category, setCategory] = useState<StyleCategory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exists, setExists] = useState<string | null>(null);
  const propose = usePropose();
  const toast = useToast();
  const ready = name.trim().length >= 2 && category !== null;

  // Ogni apertura riparte dal nome suggerito (es. quello cercato).
  useEffect(() => {
    if (visible) setName(initialName);
  }, [visible, initialName]);

  const submit = () => {
    if (!ready || !category) return;
    setError(null);
    setExists(null);
    propose.mutate(
      { name, category, tagline },
      {
        onSuccess: (result) => {
          toast.show(
            result.created
              ? t("Proposta inviata: servono {threshold} richieste.", { threshold: result.proposal.threshold })
              : t("«{name}» era già proposto: hai aggiunto la tua richiesta.", { name: result.proposal.name }),
          );
          setName("");
          setTagline("");
          setCategory(null);
          onClose();
        },
        onError: (e) => {
          setExists(existingStyle(e));
          setError(proposalError(e));
        },
      },
    );
  };

  return (
    <Sheet visible={visible} title={t("Proponi uno stile")} onClose={onClose}>
      <View style={styles.form}>
        <Text style={styles.label}>{t("NOME")}</Text>
        <TextInput
          aria-label={t("Nome dello stile")}
          value={name}
          onChangeText={(v) => {
            setName(v);
            setError(null);
            setExists(null);
          }}
          placeholder={t("Es. Avant-garde")}
          placeholderTextColor={colors.textTertiary}
          selectionColor={colors.accent}
          maxLength={NAME_MAX}
          style={styles.input}
        />
        <Text style={styles.label}>{t("CATEGORIA")}</Text>
        <View style={styles.cats} role="radiogroup" aria-label={t("Categoria")}>
          {CATEGORIES.map((c) => {
            const selected = c.key === category;
            return (
              <Pressable
                key={c.key}
                role="radio"
                aria-checked={selected}
                onPress={() => setCategory(c.key)}
                style={[styles.cat, selected && styles.catOn]}
              >
                <Text style={[styles.catText, selected && styles.catTextOn]}>{t(c.label)}</Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.label}>{t("DESCRIZIONE (OPZ.)")}</Text>
        <TextInput
          aria-label={t("Descrizione dello stile")}
          value={tagline}
          onChangeText={setTagline}
          placeholder={t("Tre parole: capi, colori, mood")}
          placeholderTextColor={colors.textTertiary}
          selectionColor={colors.accent}
          maxLength={TAGLINE_MAX}
          style={styles.input}
        />
        {error ? (
          <Text style={styles.error} role="alert">
            {error}
          </Text>
        ) : null}
        {exists ? (
          <Button
            label={onExisting ? t("Scegli questo stile") : t("Apri lo stile")}
            variant="secondary"
            size="md"
            onPress={() => {
              onClose();
              if (onExisting) onExisting(exists);
              else router.push({ pathname: "/style/[slug]", params: { slug: exists } });
            }}
          />
        ) : null}
        <Button label={t("Proponi")} onPress={submit} disabled={!ready} loading={propose.isPending} fullWidth size="md" />
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  form: { gap: spacing[2] },
  label: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 1.4, color: colors.textSecondary, marginTop: spacing[2] },
  input: {
    height: 48,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceRaised,
    color: colors.text,
    paddingHorizontal: 14,
    fontFamily: fonts.ui,
    fontSize: fontSizes.body,
    outlineWidth: 0,
  },
  cats: { flexDirection: "row", flexWrap: "wrap", gap: spacing[2] },
  cat: { height: 36, paddingHorizontal: 14, borderRadius: 18, borderWidth: 1, borderColor: colors.border, justifyContent: "center" },
  catOn: { backgroundColor: colors.text, borderColor: colors.text },
  catText: { fontFamily: fonts.uiBold, fontSize: 13, color: colors.textSecondary },
  catTextOn: { color: colors.background },
  error: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 18, color: colors.danger, marginTop: spacing[2] },
});
