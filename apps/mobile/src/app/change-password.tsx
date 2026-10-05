import { colors, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useState } from "react";
import { ScrollView, StyleSheet } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { authErrorMessage } from "@/features/auth/authErrors";
import { NewPasswordFields } from "@/features/auth/NewPasswordFields";
import { saveNewPassword } from "@/features/auth/recovery";
import { pingDevice } from "@/features/privacy/api";
import { supabase } from "@/lib/supabase";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";
import { TopBar } from "@/ui/TopBar";
import { useToast } from "@/ui/Toast";

/** Cambia password: serve quella attuale; poi si esce da tutti gli altri dispositivi. */
export default function ChangePasswordScreen() {
  const { session } = useAuth();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const email = session?.user.email;

  const save = async (password: string): Promise<string | null> => {
    if (!email) return "Il cambio password è disponibile per gli account con email.";
    const check = await supabase.auth.signInWithPassword({ email, password: current });
    if (check.error) return "La password attuale non è corretta.";
    const failed = await saveNewPassword(password);
    if (failed) return authErrorMessage(failed);
    const { data } = await supabase.auth.getSession();
    if (data.session) await pingDevice(data.session.access_token).catch(() => undefined);
    toast.show("Password cambiata. Sei uscito da tutti gli altri dispositivi.");
    router.back();
    return null;
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title="Cambia password" fallback="/settings" />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text variant="secondary">
          Dopo il cambio esci da tutti gli altri dispositivi: lì servirà la nuova password.
        </Text>
        <NewPasswordFields
          submitLabel="Salva la nuova password"
          onSubmit={save}
          ready={current.length > 0}
          before={
            <TextField
              label="PASSWORD ATTUALE"
              value={current}
              onChangeText={setCurrent}
              secure
              autoCapitalize="none"
              autoCorrect={false}
              autoComplete="current-password"
              textContentType="password"
            />
          }
        />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], gap: spacing[4], paddingBottom: spacing[8] },
});
