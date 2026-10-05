import type { Capsule } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";

import { capsuleError, useCapsuleActions, useCapsules } from "@/features/portfolio/api";
import { Button } from "@/ui/Button";
import { IconButton } from "@/ui/IconButton";
import { IconPencil, IconTrash } from "@/ui/icons";
import { Sheet } from "@/ui/Sheet";
import { TextField } from "@/ui/TextField";

export const MAX_CAPSULES = 12;
const NAME_MAX = 30;

type Props = { visible: boolean; onClose: () => void };

/** Capsule del portfolio: crea, rinomina, elimina (i fit restano nel portfolio). */
export function CapsuleManager({ visible, onClose }: Props) {
  const capsules = useCapsules(visible);
  const { create } = useCapsuleActions();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const list = capsules.data ?? [];
  const full = list.length >= MAX_CAPSULES;

  const add = () => {
    setError(null);
    create.mutate(name, {
      onSuccess: () => setName(""),
      onError: (e) => setError(capsuleError(e)),
    });
  };

  return (
    <Sheet visible={visible} title="Capsule" onClose={onClose}>
      <Text style={styles.intro}>
        Raccolte dentro il portfolio, come Estate, Serate, Ufficio. Ogni fit sta in una capsula al massimo.
      </Text>
      <View style={styles.newRow}>
        <View style={styles.flex}>
          <TextField
            label={`Nuova capsula · ${list.length} di ${MAX_CAPSULES}`}
            value={name}
            onChangeText={(value) => {
              setName(value);
              setError(null);
            }}
            placeholder="Es. Serate"
            maxLength={NAME_MAX}
            editable={!full}
            error={error}
            hint={full ? "Hai raggiunto il massimo di capsule." : undefined}
            returnKeyType="done"
            onSubmitEditing={() => name.trim() && !full && add()}
          />
        </View>
        <View style={styles.addButton}>
          <Button label="Aggiungi" size="md" onPress={add} disabled={!name.trim() || full} loading={create.isPending} />
        </View>
      </View>
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
        {list.length === 0 && capsules.isSuccess ? (
          <Text style={styles.empty}>Ancora nessuna capsula.</Text>
        ) : null}
        {list.map((capsule) => (
          <CapsuleRow key={capsule.id} capsule={capsule} />
        ))}
      </ScrollView>
    </Sheet>
  );
}

function CapsuleRow({ capsule }: { capsule: Capsule }) {
  const { rename, remove } = useCapsuleActions();
  const [mode, setMode] = useState<"view" | "edit" | "delete">("view");
  const [name, setName] = useState(capsule.name);
  const [error, setError] = useState<string | null>(null);
  const count = capsule.post_count === 1 ? "1 fit" : `${capsule.post_count} fit`;

  if (mode === "edit") {
    return (
      <View style={styles.rowEdit}>
        <TextField
          label="Rinomina"
          value={name}
          onChangeText={(value) => {
            setName(value);
            setError(null);
          }}
          maxLength={NAME_MAX}
          error={error}
          autoFocus
        />
        <View style={styles.actions}>
          <Button label="Annulla" variant="ghost" size="sm" onPress={() => setMode("view")} />
          <Button
            label="Salva"
            size="sm"
            disabled={!name.trim()}
            loading={rename.isPending}
            onPress={() =>
              rename.mutate(
                { id: capsule.id, name },
                { onSuccess: () => setMode("view"), onError: (e) => setError(capsuleError(e)) },
              )
            }
          />
        </View>
      </View>
    );
  }

  if (mode === "delete") {
    return (
      <View style={styles.rowEdit} role="alert">
        <Text style={styles.confirm}>
          Eliminare «{capsule.name}»? I fit restano nel portfolio, escono solo dalla capsula.
        </Text>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <View style={styles.actions}>
          <Button label="Annulla" variant="ghost" size="sm" onPress={() => setMode("view")} />
          <Button
            label="Elimina"
            variant="danger"
            size="sm"
            loading={remove.isPending}
            onPress={() => remove.mutate(capsule.id, { onError: (e) => setError(capsuleError(e)) })}
          />
        </View>
      </View>
    );
  }

  return (
    <View style={styles.row}>
      <View style={styles.flex}>
        <Text style={styles.name} numberOfLines={1}>
          {capsule.name}
        </Text>
        <Text style={styles.count}>{count}</Text>
      </View>
      <IconButton label={`Rinomina ${capsule.name}`} onPress={() => setMode("edit")}>
        <IconPencil color={colors.textSecondary} />
      </IconButton>
      <IconButton label={`Elimina ${capsule.name}`} onPress={() => setMode("delete")}>
        <IconTrash color={colors.textSecondary} />
      </IconButton>
    </View>
  );
}

const styles = StyleSheet.create({
  intro: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textSecondary },
  newRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing[2] },
  flex: { flex: 1, minWidth: 0 },
  addButton: { paddingTop: 22 },
  list: { maxHeight: 320 },
  listContent: { gap: spacing[2], paddingBottom: spacing[2] },
  empty: { fontFamily: fonts.ui, fontSize: 14, color: colors.textTertiary, paddingVertical: spacing[3] },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
    paddingLeft: 14,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.background,
  },
  rowEdit: {
    gap: spacing[2],
    padding: 12,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.background,
  },
  name: { fontFamily: fonts.uiBold, fontSize: 15, color: colors.text },
  count: { fontFamily: fonts.mono, fontSize: 11, color: colors.textSecondary, marginTop: 2 },
  actions: { flexDirection: "row", justifyContent: "flex-end", gap: spacing[2] },
  confirm: { fontFamily: fonts.ui, fontSize: 14, lineHeight: 20, color: colors.text },
  error: { fontFamily: fonts.ui, fontSize: 13, color: colors.danger },
});
