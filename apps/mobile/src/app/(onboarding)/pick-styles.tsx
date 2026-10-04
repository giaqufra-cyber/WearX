import { useQueryClient } from "@tanstack/react-query";
import { colors, fonts, spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { useMemo, useState } from "react";
import { StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { ME_QUERY_KEY, useAuth } from "@/features/auth/AuthProvider";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { useNicknameAvailability } from "@/features/auth/useNicknameAvailability";
import { createProfile, useAgeStatus } from "@/features/onboarding/api";
import { useAppConfig } from "@/features/styles/useAppConfig";
import { ApiError } from "@/lib/api";
import { Button } from "@/ui/Button";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { Screen } from "@/ui/Screen";
import { StyleTile } from "@/ui/StyleTile";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";
import { useToast } from "@/ui/Toast";

const NICK_ERRORS: Record<string, string> = {
  "nickname.taken": "Nel frattempo qualcuno ha preso questo nickname. Scegline un altro.",
  "nickname.reserved": "Questo nickname non è disponibile. Scegline un altro.",
  "nickname.invalid": "Questo nickname non è valido. Scegline un altro.",
};

/** Passo 4 di 4: stili da seguire, poi si crea il profilo (prototipo, "In che stile ti senti oggi?"). */
export default function PickStylesScreen() {
  const { session } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const config = useAppConfig();
  const age = useAgeStatus();
  const draft = useSignupDraft();
  const metadataNick = session?.user.user_metadata?.nickname;
  const [nickname, setNickname] = useState(
    draft.nickname || (typeof metadataNick === "string" ? metadataNick : ""),
  );
  const [nickError, setNickError] = useState<string | null>(null);
  const [editNick, setEditNick] = useState(nickname === "");
  const [selected, setSelected] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const availability = useNicknameAvailability(editNick ? nickname : "");

  const isAdult = age.data?.age_band === "18_plus";
  const styles_ = useMemo(
    () => (config.data?.styles ?? []).filter((s) => isAdult || s.min_age_band !== "18_plus"),
    [config.data, isAdult],
  );

  if (config.isPending || age.isPending) {
    return (
      <Screen>
        <Loading label="Carichiamo gli stili…" />
      </Screen>
    );
  }
  if (config.isError || age.isError) {
    return (
      <Screen>
        <AuthHeader step="PASSO 4 DI 4" />
        <ErrorNotice error={config.error ?? age.error} />
      </Screen>
    );
  }

  const toggle = (slug: string) =>
    setSelected((prev) => (prev.includes(slug) ? prev.filter((s) => s !== slug) : [...prev, slug]));

  const submit = async () => {
    const token = session?.access_token;
    if (!token || selected.length === 0 || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const profile = await createProfile(token, {
        nickname: nickname.trim().toLowerCase(),
        terms_version: config.data.terms_version,
        // Consenso dato al passo 1 (casella delle regole della community).
        accept_community_rules: true,
        styles: selected,
        account_type: draft.accountType,
      });
      useSignupDraft.getState().clear(); // la data di nascita sparisce dalla memoria
      await queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY });
      toast.show(`Benvenuto su WearX, @${profile.nickname}.`);
    } catch (caught) {
      const code = caught instanceof ApiError ? caught.code : "";
      if (NICK_ERRORS[code]) {
        setEditNick(true);
        setNickError(NICK_ERRORS[code]);
      } else if (code === "age.verification_required") {
        router.replace("/age");
      } else if (code === "profile.exists") {
        await queryClient.invalidateQueries({ queryKey: ME_QUERY_KEY });
      } else if (code === "terms.outdated" || code === "style.not_found" || code === "style.age_restricted") {
        await config.refetch();
        setSelected([]);
        setError("Qualcosa è cambiato nel frattempo: controlla la scelta e riprova.");
      } else {
        setError("Non riusciamo a creare il profilo. Controlla la connessione e riprova.");
      }
    } finally {
      setSubmitting(false);
    }
  };

  const nickBlocked = editNick && (availability === "taken" || availability === "reserved" || nickname.length < 3);
  const rows: (typeof styles_)[] = [];
  for (let i = 0; i < styles_.length; i += 2) rows.push(styles_.slice(i, i + 2));

  return (
    <View style={styles.root}>
      <Screen>
        <AuthHeader step="PASSO 4 DI 4" />
        <Text variant="display" role="heading">
          In che stile{"\n"}ti senti oggi?
        </Text>
        <Text variant="secondary">
          Nel feed vedrai solo fit di questi stili. Puoi entrare e uscire quando vuoi, anche solo per una serata.
        </Text>

        {editNick ? (
          <TextField
            label="NICKNAME"
            prefix="@"
            value={nickname}
            onChangeText={(value) => {
              setNickname(value.toLowerCase());
              setNickError(null);
            }}
            autoCapitalize="none"
            autoCorrect={false}
            maxLength={20}
            error={
              nickError ?? (availability === "taken" ? "Già preso. Prova una variante." : null)
            }
            hint={availability === "available" ? "Libero." : "Minuscole, numeri, punto e underscore."}
            hintColor={availability === "available" ? colors.accent : undefined}
          />
        ) : null}

        <View style={styles.grid}>
          {rows.map((row) => (
            <View key={row.map((s) => s.slug).join("|")} style={styles.row}>
              {row.map((style) => (
                <StyleTile
                  key={style.slug}
                  name={style.name}
                  tagline={style.tagline}
                  tone={style.tone}
                  selectable
                  selected={selected.includes(style.slug)}
                  onPress={() => toggle(style.slug)}
                  badge={style.seasonal ? "Stagionale" : style.min_age_band === "18_plus" ? "18+" : undefined}
                />
              ))}
              {row.length === 1 ? <View style={styles.filler} /> : null}
            </View>
          ))}
        </View>
        {error ? (
          <Text variant="secondary" color={colors.danger} role="alert">
            {error}
          </Text>
        ) : null}
        <View style={styles.bottomSpace} />
      </Screen>

      <SafeAreaView edges={["bottom"]} style={styles.bar}>
        <Text style={styles.count} aria-live="polite">
          {selected.length === 1 ? "1 STILE" : `${selected.length} STILI`}
        </Text>
        <Button
          label="Entra in WearX"
          onPress={() => void submit()}
          disabled={selected.length === 0 || nickBlocked}
          loading={submitting}
          size="md"
        />
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  grid: { gap: 10, marginTop: spacing[3] },
  row: { flexDirection: "row", gap: 10 },
  filler: { flex: 1 },
  bottomSpace: { height: 80 },
  bar: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing[4],
    paddingTop: spacing[3],
    paddingBottom: spacing[3],
    backgroundColor: colors.background,
    borderTopWidth: 1,
    borderTopColor: colors.borderSubtle,
  },
  count: { fontFamily: fonts.mono, fontSize: 12, letterSpacing: 1.5, color: colors.textSecondary },
});
