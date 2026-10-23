import type { AgeMethod, AgeStatus } from "@wearx/api-types";
import { colors, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { type ReactNode, useEffect, useState } from "react";
import { StyleSheet, View } from "react-native";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { useAuth } from "@/features/auth/AuthProvider";
import { BirthDateFields, type BirthValue } from "@/features/auth/BirthDateFields";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { ageReturnUrl, isoDate, startAgeSession, useAgeStatus } from "@/features/onboarding/api";
import { MethodCard } from "@/features/onboarding/MethodCard";
import { ApiError } from "@/lib/api";
import { ageOn, MIN_AGE } from "@/lib/validation";
import { EmptyState } from "@/ui/EmptyState";
import { IconDocument, IconFaceScan, IconIdCard, IconLock, IconShield } from "@/ui/icons";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { N_, t } from "@/lib/i18n";

const METHODS: Record<AgeMethod, { title: string; body: string; icon: ReactNode; tag?: string }> = {
  selfie_estimation: {
    title: N_("Stima con selfie"),
    body: N_("30 secondi. La foto viene analizzata e cancellata subito."),
    icon: <IconFaceScan color={colors.text} />,
    tag: "RAPIDO",
  },
  spid: {
    title: N_("SPID"),
    body: N_("Ci arriva solo la tua età. Nessun altro dato."),
    icon: <IconIdCard color={colors.text} />,
  },
  cie: {
    title: N_("CIE"),
    body: N_("Carta d'identità elettronica. Ci arriva solo la tua età."),
    icon: <IconIdCard color={colors.text} />,
  },
  id_document: {
    title: N_("Documento d'identità"),
    body: N_("Verifica tramite partner certificato, documento non conservato."),
    icon: <IconDocument color={colors.text} />,
  },
};

/** Messaggio sull'ultimo tentativo, se non è andato a buon fine. */
function lastAttemptNote(latest: AgeStatus["latest"]): string | null {
  if (!latest) return null;
  if (latest.status === "expired") return t("La verifica precedente è scaduta. Puoi riprovare.");
  if (latest.status !== "failed") return null;
  if (latest.failure_reason === "inconsistent") {
    return t("La stima non è bastata a confermare la tua età. Usa un documento per completare.");
  }
  if (latest.failure_reason === "not_completed") return t("Verifica non completata. Puoi riprovare quando vuoi.");
  return null;
}

/** Passo 2 di 4: verifica dell'età con il fornitore (prototipo, "Confermiamo che hai 16+"). */
export default function AgeScreen() {
  const { session, signOut } = useAuth();
  const draftBirth = useSignupDraft((s) => s.birth);
  const status = useAgeStatus();
  const [birth, setBirth] = useState<BirthValue>({ day: "", month: "", year: "" });
  const [starting, setStarting] = useState<AgeMethod | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [blocked, setBlocked] = useState(false);

  const verified = status.data?.verified === true;
  useEffect(() => {
    if (verified) router.replace("/profile-type");
  }, [verified]);

  if (status.isPending || verified) {
    return (
      <Screen>
        <Loading label={t("Un attimo…")} />
      </Screen>
    );
  }
  if (status.isError) {
    return (
      <Screen>
        <AuthHeader step={t("PASSO {n} DI 4", { n: 2 })} onBack={() => void signOut()} />
        <ErrorNotice error={status.error} />
      </Screen>
    );
  }

  const latest = status.data.latest;
  if (blocked || (latest?.status === "failed" && latest.failure_reason === "underage")) {
    return (
      <Screen>
        <AuthHeader onBack={null} />
        <EmptyState
          title={t("WearX è per chi ha 16 anni o più")}
          body={t("La verifica dice che non hai ancora l'età per usare WearX. Ti aspettiamo più avanti.")}
          action={{ label: t("Esci"), onPress: () => void signOut() }}
        />
      </Screen>
    );
  }

  // Data dichiarata in registrazione; se l'app è stata riaperta va reinserita (non la salviamo).
  const typed =
    birth.day && birth.month && birth.year.length === 4
      ? { day: Number(birth.day), month: Number(birth.month), year: Number(birth.year) }
      : null;
  const declared = draftBirth ?? typed;
  const declaredAge = declared ? ageOn(declared.day, declared.month, declared.year, new Date()) : null;
  const birthProblem =
    !draftBirth && typed && declaredAge === null
      ? t("Questa data non esiste.")
      : declaredAge !== null && declaredAge < MIN_AGE
        ? t("WearX è riservata a chi ha almeno 16 anni.")
        : null;
  const ready = declared !== null && declaredAge !== null && declaredAge >= MIN_AGE;

  const note = lastAttemptNote(latest);
  const methods = [...status.data.methods];
  if (latest?.failure_reason === "inconsistent") {
    // Dopo una stima non sufficiente si propongono prima i metodi con documento.
    methods.sort((a, b) => Number(a === "selfie_estimation") - Number(b === "selfie_estimation"));
  }

  const start = async (method: AgeMethod) => {
    const token = session?.access_token;
    if (!token || !declared || !ready) return;
    setStarting(method);
    setError(null);
    try {
      const created = await startAgeSession(token, method, isoDate(declared));
      if (created.redirect_url) {
        await WebBrowser.openAuthSessionAsync(created.redirect_url, ageReturnUrl());
      }
      router.push("/age-wait");
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === "age.blocked") setBlocked(true);
      else if (caught instanceof ApiError && caught.code === "age.already_verified") void status.refetch();
      else if (caught instanceof ApiError && caught.status === 429) setError(t("Troppi tentativi. Riprova tra un'ora."));
      else setError(t("Non riusciamo ad avviare la verifica. Controlla la connessione e riprova."));
    } finally {
      setStarting(null);
    }
  };

  return (
    <Screen>
      <AuthHeader step={t("PASSO {n} DI 4", { n: 2 })} onBack={() => void signOut()} />
      <View style={styles.badge}>
        <IconShield color={colors.accent} size={32} />
      </View>
      <Text variant="display" role="heading">
        {t("Confermiamo\nche hai 16+")}
      </Text>
      <Text variant="secondary">
        {t("Lo facciamo una volta sola, così la community resta sicura. Scegli il metodo che preferisci.")}
      </Text>

      {note ? (
        <Text variant="secondary" color={colors.warning} role="alert">
          {note}
        </Text>
      ) : null}

      {!draftBirth ? (
        <View style={styles.group}>
          <Text variant="secondary">{t("Per sicurezza non teniamo la data di nascita: inseriscila di nuovo.")}</Text>
          <BirthDateFields value={birth} onChange={(patch) => setBirth((prev) => ({ ...prev, ...patch }))} />
          {birthProblem ? (
            <Text variant="secondary" color={colors.danger} role="alert">
              {birthProblem}
            </Text>
          ) : null}
        </View>
      ) : null}

      <View style={styles.methods}>
        {methods.map((method) => (
          <MethodCard
            key={method}
            {...METHODS[method]}
            tag={latest?.failure_reason === "inconsistent" ? undefined : METHODS[method].tag}
            onPress={() => void start(method)}
            disabled={!ready || (starting !== null && starting !== method)}
            loading={starting === method}
          />
        ))}
      </View>

      {error ? (
        <Text variant="secondary" color={colors.danger} role="alert">
          {error}
        </Text>
      ) : null}

      <View style={styles.privacy}>
        <IconLock color={colors.textTertiary} />
        <Text variant="secondary" style={styles.privacyText} color={colors.textTertiary}>
          {t("Nessun dato biometrico viene salvato. Teniamo solo l'esito della verifica, cifrato.")}
        </Text>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  badge: {
    width: 64,
    height: 64,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    marginTop: spacing[2],
  },
  group: { gap: spacing[2] },
  methods: { gap: 10, marginTop: spacing[2] },
  privacy: { flexDirection: "row", gap: 10, alignItems: "flex-start", marginTop: spacing[4] },
  privacyText: { flex: 1, fontSize: 12 },
});
