import { colors, fonts, fontSizes, radii, spacing } from "@wearx/design-tokens";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ScrollView, StyleSheet, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { deviceInfo, type FeedbackKind, useSendFeedback } from "@/features/feedback/api";
import { ApiError } from "@/lib/api";
import { Button } from "@/ui/Button";
import { SegmentedControl } from "@/ui/SegmentedControl";
import { Text } from "@/ui/Text";
import { TopBar } from "@/ui/TopBar";
import { useToast } from "@/ui/Toast";

const MAX = 2000;
const KINDS = [
  { value: "bug", label: "Non funziona" },
  { value: "idea", label: "Un'idea" },
  { value: "other", label: "Altro" },
] as const;
const PLACEHOLDER: Record<FeedbackKind, string> = {
  bug: "Cosa stavi facendo, cosa ti aspettavi, cosa è successo invece.",
  idea: "Cosa ti piacerebbe trovare in WearX?",
  other: "Scrivi qui.",
};

/** Segnala un problema (beta, seduta 25): il messaggio arriva al team nel pannello dello staff. */
export default function FeedbackScreen() {
  const { from } = useLocalSearchParams<{ from?: string }>();
  const toast = useToast();
  const send = useSendFeedback();
  const [kind, setKind] = useState<FeedbackKind>("bug");
  const [message, setMessage] = useState("");
  const info = deviceInfo();
  const system = info.platform === "ios" ? "iOS" : info.platform === "android" ? "Android" : "Web";
  const tooMany = send.error instanceof ApiError && send.error.status === 429;
  const ready = message.trim().length >= 3 && !send.isPending;

  const submit = () =>
    send.mutate(
      { kind, message, screen: typeof from === "string" ? from : null },
      {
        onSuccess: () => {
          toast.show("Grazie! Il messaggio è arrivato al team di WearX.");
          router.back();
        },
      },
    );

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title="Segnala un problema" fallback="/settings" />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text variant="secondary">
          WearX è in prova: ogni messaggio lo leggiamo noi del team. Non serve essere precisi, basta raccontare.
        </Text>
        <SegmentedControl label="Di cosa si tratta" options={KINDS} value={kind} onChange={setKind} />
        <View style={styles.field}>
          <Text variant="label" nativeID="feedback-label">
            IL TUO MESSAGGIO
          </Text>
          <TextInput
            value={message}
            onChangeText={setMessage}
            placeholder={PLACEHOLDER[kind]}
            placeholderTextColor={colors.textTertiary}
            selectionColor={colors.accent}
            maxLength={MAX}
            multiline
            textAlignVertical="top"
            aria-label="Il tuo messaggio"
            style={styles.input}
          />
          <Text variant="label" style={styles.counter}>
            {message.length}/{MAX}
          </Text>
        </View>
        <Text variant="secondary" style={styles.note}>
          Insieme al messaggio mandiamo solo la versione dell&apos;app ({info.app_version}), il sistema ({system}
          {info.os_version ? ` ${info.os_version}` : ""}){from ? " e la schermata da cui sei partito" : ""}. Per una
          schermata, su iPhone puoi anche scattare uno screenshot e inviarlo da TestFlight.
        </Text>
        {tooMany ? (
          <Text color={colors.danger} role="alert">
            Hai già mandato 10 messaggi oggi: riprova domani.
          </Text>
        ) : send.isError ? (
          <Text color={colors.danger} role="alert">
            Messaggio non inviato. Controlla la connessione e riprova.
          </Text>
        ) : null}
        <Button label="Invia al team" onPress={submit} disabled={!ready} loading={send.isPending} fullWidth />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], gap: spacing[4], paddingBottom: spacing[8] },
  field: { gap: spacing[2] },
  input: {
    minHeight: 160,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
    color: colors.text,
    padding: 14,
    fontFamily: fonts.ui,
    fontSize: fontSizes.bodyLarge,
    outlineWidth: 0,
  },
  counter: { alignSelf: "flex-end" },
  note: { fontSize: 12, lineHeight: 18 },
});
