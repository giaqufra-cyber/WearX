import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { MAX_CAPSULES } from "@/features/portfolio/CapsuleManager";
import { capsuleError, useCapsuleActions, useCapsules } from "@/features/portfolio/api";
import { Button } from "@/ui/Button";
import { IconCheck } from "@/ui/icons";
import { Sheet } from "@/ui/Sheet";
import { TextField } from "@/ui/TextField";

type Props = {
  visible: boolean;
  current: string | null;
  busy: boolean;
  onPick: (capsuleId: string | null) => void;
  onClose: () => void;
};

/** In quale capsula mettere un fit; si può crearne una nuova al volo. */
export function CapsulePicker({ visible, current, busy, onPick, onClose }: Props) {
  const capsules = useCapsules(visible);
  const { create } = useCapsuleActions();
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const list = capsules.data ?? [];
  const options = [{ id: null, name: "Nessuna capsula" }, ...list];

  return (
    <Sheet visible={visible} title="Capsula" onClose={onClose}>
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
        <View role="radiogroup" aria-label="Capsula del fit" style={styles.listContent}>
          {options.map((option) => {
            const selected = option.id === current;
            return (
              <Pressable
                key={option.id ?? "none"}
                role="radio"
                aria-checked={selected}
                disabled={busy}
                onPress={() => onPick(option.id)}
                style={[styles.option, selected && styles.optionOn]}
              >
                <Text style={[styles.optionText, option.id === null && styles.optionNone]}>{option.name}</Text>
                {selected ? <IconCheck color={colors.accent} size={18} /> : null}
              </Pressable>
            );
          })}
        </View>
      </ScrollView>
      {list.length < MAX_CAPSULES ? (
        <View style={styles.newRow}>
          <View style={styles.flex}>
            <TextField
              label="Oppure creane una"
              value={name}
              onChangeText={(value) => {
                setName(value);
                setError(null);
              }}
              placeholder="Es. Estate"
              maxLength={30}
              error={error}
            />
          </View>
          <View style={styles.add}>
            <Button
              label="Crea e aggiungi"
              size="md"
              disabled={!name.trim() || busy}
              loading={create.isPending}
              onPress={() =>
                create.mutate(name, {
                  onSuccess: (capsule) => {
                    setName("");
                    onPick(capsule.id);
                  },
                  onError: (e) => setError(capsuleError(e)),
                })
              }
            />
          </View>
        </View>
      ) : null}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  list: { maxHeight: 300 },
  listContent: { gap: spacing[2] },
  option: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.background,
  },
  optionOn: { borderColor: colors.accent },
  optionText: { fontFamily: fonts.uiBold, fontSize: 15, color: colors.text },
  optionNone: { fontFamily: fonts.ui, color: colors.textSecondary },
  newRow: { flexDirection: "row", alignItems: "flex-start", gap: spacing[2] },
  flex: { flex: 1, minWidth: 0 },
  add: { paddingTop: 22 },
});
