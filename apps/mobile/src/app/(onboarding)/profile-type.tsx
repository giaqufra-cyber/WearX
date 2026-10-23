import { spacing } from "@wearx/design-tokens";
import { router } from "expo-router";
import { StyleSheet, View } from "react-native";

import { AuthHeader } from "@/features/auth/AuthHeader";
import { useSignupDraft } from "@/features/auth/signupDraft";
import { useAgeStatus } from "@/features/onboarding/api";
import { ChoiceCard } from "@/features/onboarding/MethodCard";
import { useAppConfig } from "@/features/styles/useAppConfig";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { t } from "@/lib/i18n";

/** Passo 3 di 4: profilo privato o Business (prototipo, "Che profilo vuoi?"). */
export default function ProfileTypeScreen() {
  const accountType = useSignupDraft((s) => s.accountType);
  const setDraft = useSignupDraft((s) => s.set);
  const age = useAgeStatus();
  const config = useAppConfig();

  const isAdult = age.data?.age_band === "18_plus";
  const businessOn = config.data?.feature_flags.business_accounts === true;
  const businessNote = !businessOn
    ? t("In arrivo: per ora si parte con un profilo privato.")
    : !isAdult
      ? t("Il profilo Business è solo per maggiorenni.")
      : undefined;
  const businessAllowed = businessNote === undefined;
  const selected = accountType === "business" && businessAllowed ? "business" : "private";

  return (
    <Screen>
      {/* Dalla verifica dell'età non si torna indietro: è già fatta. */}
      <AuthHeader step={t("PASSO {n} DI 4", { n: 3 })} onBack={null} />
      <Text variant="display" role="heading">
        {t("Che profilo\nvuoi?")}
      </Text>
      <Text variant="secondary">{t("Puoi cambiarlo quando vuoi dalle impostazioni.")}</Text>

      <View style={styles.cards} role="radiogroup" aria-label={t("Tipo di profilo")}>
        <ChoiceCard
          title={t("Privato")}
          body={t("Il tuo portfolio lo vede solo chi approvi. I tuoi fit nei feed degli stili restano anonimi fino a quando non li apri.")}
          selected={selected === "private"}
          onPress={() => setDraft({ accountType: "private" })}
        />
        <ChoiceCard
          title={t("Business")}
          body={t("Per brand, negozi e creator. Profilo pubblico, link shop verificati e insight sui click ai negozi.")}
          selected={selected === "business"}
          onPress={() => setDraft({ accountType: "business" })}
          disabled={!businessAllowed}
          note={businessNote}
        />
      </View>

      <Button
        label={t("Continua")}
        onPress={() => {
          setDraft({ accountType: selected });
          router.push("/pick-styles");
        }}
        fullWidth
      />
    </Screen>
  );
}

const styles = StyleSheet.create({ cards: { gap: spacing[3], marginVertical: spacing[3] } });
