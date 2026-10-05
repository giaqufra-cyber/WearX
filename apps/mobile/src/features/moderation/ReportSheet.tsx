import type { ReportReason, ReportReceipt } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { REASONS, type ReportTarget, reportError, reviewLabel, useReport } from "@/features/moderation/api";
import { Button } from "@/ui/Button";
import { IconCheck } from "@/ui/icons";
import { Sheet } from "@/ui/Sheet";
import { TextField } from "@/ui/TextField";

type Props = { target: ReportTarget; visible: boolean; onClose: () => void };

/** Segnala un fit o un profilo: motivo, dettagli facoltativi, conferma con i tempi di revisione. */
export function ReportSheet({ target, visible, onClose }: Props) {
  const report = useReport(target);
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [details, setDetails] = useState("");
  const [done, setDone] = useState<ReportReceipt | null>(null);
  const [error, setError] = useState<string | null>(null);

  const close = () => {
    onClose();
    setReason(null);
    setDetails("");
    setDone(null);
    setError(null);
  };
  const title = target.type === "post" ? "Segnala il fit" : `Segnala @${target.nickname}`;

  return (
    <Sheet visible={visible} title={done ? "Grazie" : title} onClose={close}>
      {done ? (
        <View style={styles.done} role="alert">
          <Text style={styles.text}>
            Segnalazione ricevuta: una persona la controlla {reviewLabel(done.review_within_hours)}. Non diciamo a
            nessuno chi l'ha fatta.
          </Text>
          {reason === "minor_safety" ? (
            <Text style={styles.urgent}>Se qualcuno è in pericolo adesso, chiama il 112.</Text>
          ) : null}
          <Text style={styles.hint}>Puoi anche bloccare la persona dal suo profilo.</Text>
          <Button label="Chiudi" variant="secondary" size="md" fullWidth onPress={close} />
        </View>
      ) : (
        <>
          <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
            <View role="radiogroup" aria-label="Motivo della segnalazione" style={styles.listContent}>
              {REASONS.map((r) => {
                const selected = r.value === reason;
                return (
                  <Pressable
                    key={r.value}
                    role="radio"
                    aria-checked={selected}
                    aria-label={r.label}
                    onPress={() => setReason(r.value)}
                    style={[styles.option, selected && styles.optionOn]}
                  >
                    <View style={styles.flex}>
                      <Text style={styles.label}>{r.label}</Text>
                      <Text style={styles.optionHint}>{r.hint}</Text>
                    </View>
                    {selected ? <IconCheck color={colors.accent} size={18} /> : null}
                  </Pressable>
                );
              })}
            </View>
          </ScrollView>
          {reason ? (
            <TextField
              label="Dettagli (facoltativi)"
              value={details}
              onChangeText={setDetails}
              maxLength={500}
              multiline
              placeholder="Cosa è successo?"
              error={error}
            />
          ) : null}
          <Button
            label="Invia segnalazione"
            size="md"
            fullWidth
            disabled={!reason}
            loading={report.isPending}
            onPress={() =>
              reason &&
              report.mutate(
                { reason, details },
                { onSuccess: setDone, onError: (e) => setError(reportError(e)) },
              )
            }
          />
        </>
      )}
    </Sheet>
  );
}

const styles = StyleSheet.create({
  list: { maxHeight: 330 },
  listContent: { gap: 6 },
  option: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing[2],
    minHeight: 52,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.background,
  },
  optionOn: { borderColor: colors.accent },
  flex: { flex: 1 },
  label: { fontFamily: fonts.uiBold, fontSize: 14, color: colors.text },
  optionHint: { fontFamily: fonts.ui, fontSize: 12, color: colors.textSecondary, marginTop: 2 },
  done: { gap: spacing[3] },
  text: { fontFamily: fonts.ui, fontSize: 15, lineHeight: 21, color: colors.text },
  urgent: { fontFamily: fonts.uiBold, fontSize: 14, color: colors.warning },
  hint: { fontFamily: fonts.ui, fontSize: 13, color: colors.textSecondary },
});
