/**
 * Solo per la demo sul telefono (EXPO_PUBLIC_DEMO=1, build per Sideloadly): prima di tutto il
 * resto l'app deve sapere a quale server collegarsi. Fuori dalla demo, o sul web, non fa nulla.
 */
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import * as Linking from "expo-linking";
import * as SplashScreen from "expo-splash-screen";
import { Fragment, type ReactNode, useEffect, useRef, useState } from "react";
import { Platform, StyleSheet, Text as RNText, View } from "react-native";

import { connectDemo, startDemo, useDemoStore } from "@/features/demo/demoStore";
import { serverFromLink } from "@/features/demo/server";
import { env } from "@/lib/env";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";

type Props = {
  /** Font caricati: la schermata di collegamento usa quelli del brand. */
  ready: boolean;
  /** Chiamata quando si passa a un altro server (es. per svuotare la cache dei dati). */
  onServerChange?: () => void;
  children: ReactNode;
};

export function DemoGate(props: Props) {
  if (!env.demo || Platform.OS === "web") return <>{props.children}</>;
  return <NativeDemoGate {...props} />;
}

function NativeDemoGate({ ready, onServerChange, children }: Props) {
  const phase = useDemoStore((s) => s.phase);
  const server = useDemoStore((s) => s.server);
  const previous = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Linking.getInitialURL().then((url) => {
      if (!cancelled) void startDemo(serverFromLink(url));
    });
    // QR inquadrato con l'app già aperta: ci si collega al nuovo server.
    const subscription = Linking.addEventListener("url", ({ url }) => {
      const next = serverFromLink(url);
      if (next) void connectDemo(next);
    });
    return () => {
      cancelled = true;
      subscription.remove();
    };
  }, []);

  useEffect(() => {
    if (phase !== "ready" || !server) return;
    if (previous.current && previous.current !== server) onServerChange?.();
    previous.current = server;
  }, [phase, server, onServerChange]);

  if (phase === "ready" && server) return <Fragment key={server}>{children}</Fragment>;
  if (!ready || phase === "starting") return null;
  return <DemoSetup />;
}

export function DemoSetup() {
  const phase = useDemoStore((s) => s.phase);
  const draft = useDemoStore((s) => s.draft);
  const problem = useDemoStore((s) => s.problem);
  const [value, setValue] = useState(draft);

  useEffect(() => {
    void SplashScreen.hideAsync();
  }, []);
  useEffect(() => setValue(draft), [draft]);

  const checking = phase === "checking";
  return (
    <Screen>
      <View style={styles.top}>
        <RNText style={styles.kicker}>WEARX · DEMO</RNText>
      </View>
      <Text variant="display" role="heading">
        Collega la demo
      </Text>
      <Text variant="secondary">
        Sul computer avvia la demo (scripts/demo.sh). Poi inquadra il primo QR con la Fotocamera
        dell&apos;iPhone, oppure incolla qui il link che finisce con trycloudflare.com.
      </Text>
      <TextField
        label="Link della demo"
        placeholder="https://….trycloudflare.com"
        value={value}
        onChangeText={setValue}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        returnKeyType="go"
        onSubmitEditing={() => void connectDemo(value)}
        error={problem}
      />
      <Button
        label={checking ? "Collegamento…" : "Collega"}
        loading={checking}
        disabled={checking || !value.trim()}
        onPress={() => void connectDemo(value)}
        fullWidth
      />
      <View style={styles.note}>
        <Text variant="label">ACCESSO PRONTO</Text>
        <Text variant="secondary">ospite@demo.test · Demo-WearX-2026!</Text>
        <Text variant="secondary">
          Per un account nuovo il codice di conferma è sempre 123456. I dati della demo si azzerano a ogni
          avvio.
        </Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  top: { paddingTop: spacing[5] },
  kicker: { fontFamily: fonts.mono, fontSize: 11, letterSpacing: 11 * 0.16, color: colors.textSecondary },
  note: {
    marginTop: spacing[4],
    gap: spacing[1],
    padding: spacing[4],
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    borderRadius: radii.md,
  },
});
