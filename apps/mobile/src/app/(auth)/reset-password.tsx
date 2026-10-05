import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useRef, useState } from "react";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { authErrorMessage } from "@/features/auth/authErrors";
import { parseAuthRedirect } from "@/features/auth/emailLink";
import { NewPasswordFields } from "@/features/auth/NewPasswordFields";
import { saveNewPassword, useRecovery } from "@/features/auth/recovery";
import { supabase } from "@/lib/supabase";
import { EmptyState } from "@/ui/EmptyState";
import { Loading } from "@/ui/LoadState";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Aperta dal link nella mail di recupero: si scambia il codice monouso, poi nuova password. */
export default function ResetPasswordScreen() {
  const params = useLocalSearchParams();
  const redirect = parseAuthRedirect(params);
  const startRecovery = useRecovery((s) => s.start);
  const finishRecovery = useRecovery((s) => s.finish);
  const [state, setState] = useState<"exchanging" | "ready" | "failed">(
    redirect?.kind === "code" ? "exchanging" : "failed",
  );
  const started = useRef<string | null>(null);
  const code = redirect?.kind === "code" ? redirect.code : null;

  useEffect(() => {
    if (!code || started.current === code) return;
    started.current = code;
    startRecovery(); // la sessione arriva, ma prima va scelta la password
    supabase.auth
      .exchangeCodeForSession(code)
      .then(({ error }) => {
        if (error) {
          finishRecovery();
          setState("failed");
        } else setState("ready");
      })
      .catch(() => {
        finishRecovery();
        setState("failed");
      });
  }, [code, startRecovery, finishRecovery]);

  if (state === "exchanging") {
    return (
      <Screen>
        <Loading label="Controllo il link…" />
      </Screen>
    );
  }
  if (state === "failed") {
    return (
      <Screen>
        <AuthHeader />
        <EmptyState
          title="Link non valido"
          body="Il link è scaduto o è già stato usato, oppure l'hai aperto da un altro dispositivo. Chiedine uno nuovo."
          action={{ label: "Chiedi un nuovo link", onPress: () => router.replace("/forgot") }}
        />
      </Screen>
    );
  }
  return (
    <Screen>
      <AuthHeader />
      <Text variant="display" role="heading">
        Nuova password
      </Text>
      <Text variant="secondary">Scegline una che non usi altrove.</Text>
      <NewPasswordFields
        submitLabel="Salva ed entra"
        onSubmit={async (password) => {
          const failed = await saveNewPassword(password);
          if (failed) return authErrorMessage(failed);
          finishRecovery();
          return null;
        }}
      />
    </Screen>
  );
}
