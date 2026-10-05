import type { ShopDomain } from "@wearx/api-types";
import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { useState } from "react";
import { ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { useAuth } from "@/features/auth/AuthProvider";
import { shopError, useShopActions, useShopDomains } from "@/features/business/api";
import { longDate } from "@/features/privacy/api";
import { Button } from "@/ui/Button";
import { IconCheck } from "@/ui/icons";
import { ErrorNotice, Loading } from "@/ui/LoadState";
import { TextField } from "@/ui/TextField";
import { TopBar } from "@/ui/TopBar";
import { useToast } from "@/ui/Toast";

/** I siti del tuo negozio: aggiungi, pubblica il file con il codice, verifica. */
export default function ShopDomainsScreen() {
  const { profile } = useAuth();
  const business = profile?.account_type === "business";
  const domains = useShopDomains(business);
  const { add, verify, remove } = useShopActions();
  const toast = useToast();
  const [draft, setDraft] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});

  if (!business) {
    return (
      <SafeAreaView style={styles.safe} edges={["top"]}>
        <TopBar title="I tuoi negozi" fallback="/settings" />
        <View style={styles.content}>
          <Text style={styles.text}>I negozi verificati sono per gli account Business.</Text>
        </View>
      </SafeAreaView>
    );
  }

  const onVerify = (domain: string) =>
    verify.mutate(domain, {
      onSuccess: () => {
        setErrors((e) => ({ ...e, [domain]: "" }));
        toast.show(`${domain} verificato.`);
      },
      onError: (error) => setErrors((e) => ({ ...e, [domain]: shopError(error) })),
    });

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <TopBar title="I tuoi negozi" fallback="/settings" />
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <Text style={styles.lead}>
          Verifica il sito del tuo negozio: i capi che puntano lì mostrano il segno di negozio verificato, e chi li apre
          lo sa.
        </Text>
        {domains.isPending ? <Loading label="Carico i tuoi siti" /> : null}
        {domains.isError ? <ErrorNotice error={domains.error} onRetry={() => void domains.refetch()} /> : null}
        {(domains.data ?? []).map((d) => (
          <DomainCard
            key={d.domain}
            domain={d}
            error={errors[d.domain]}
            verifying={verify.isPending && verify.variables === d.domain}
            onVerify={() => onVerify(d.domain)}
            onRemove={() => remove.mutate(d.domain)}
          />
        ))}
        {(domains.data?.length ?? 0) < 5 ? (
          <View style={styles.add}>
            <TextField
              label="AGGIUNGI UN SITO"
              value={draft}
              onChangeText={setDraft}
              placeholder="tuonegozio.it"
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="url"
              error={add.isError ? shopError(add.error) : null}
            />
            <Button
              label="Aggiungi"
              variant="secondary"
              disabled={draft.trim().length < 3}
              loading={add.isPending}
              onPress={() => add.mutate(draft, { onSuccess: () => setDraft("") })}
            />
          </View>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

function DomainCard({
  domain,
  error,
  verifying,
  onVerify,
  onRemove,
}: {
  domain: ShopDomain;
  error?: string;
  verifying: boolean;
  onVerify: () => void;
  onRemove: () => void;
}) {
  return (
    <View style={styles.card}>
      <View style={styles.cardHead}>
        <Text style={styles.domain}>{domain.domain}</Text>
        {domain.verified ? (
          <View style={styles.badge}>
            <IconCheck color={colors.onAccent} size={11} strokeWidth={3.2} />
            <Text style={styles.badgeText}>VERIFICATO</Text>
          </View>
        ) : (
          <Text style={styles.pending}>DA VERIFICARE</Text>
        )}
      </View>
      {domain.verified ? (
        <Text style={styles.text}>Verificato il {domain.verified_at ? longDate(domain.verified_at) : ""}.</Text>
      ) : (
        <>
          <Text style={styles.text}>Pubblica sul tuo sito un file di testo a questo indirizzo:</Text>
          <Text style={styles.code} selectable>
            {domain.file_url}
          </Text>
          <Text style={styles.text}>con dentro questa riga:</Text>
          <Text style={styles.code} selectable>
            {domain.file_content}
          </Text>
          <Text style={styles.hint}>
            Chi gestisce il sito (o il tuo servizio di e-commerce) sa come farlo. Poi tocca Verifica.
          </Text>
          {error ? (
            <Text style={styles.error} role="alert">
              {error}
            </Text>
          ) : null}
          <Button label="Verifica" size="sm" loading={verifying} onPress={onVerify} />
        </>
      )}
      <Button label="Rimuovi" size="sm" variant="ghost" onPress={onRemove} />
    </View>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing[4], gap: spacing[4], paddingBottom: spacing[8] },
  lead: { fontFamily: fonts.ui, fontSize: 15, lineHeight: 22, color: colors.text },
  card: {
    gap: spacing[2],
    padding: spacing[4],
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.borderSubtle,
    backgroundColor: colors.surface,
  },
  cardHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing[2] },
  domain: { fontFamily: fonts.uiSemiBold, fontSize: 16, color: colors.text, flexShrink: 1 },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: radii.xs,
    backgroundColor: colors.accent,
  },
  badgeText: { fontFamily: fonts.uiExtraBold, fontSize: 10, letterSpacing: 1, color: colors.onAccent },
  pending: { fontFamily: fonts.mono, fontSize: 10, letterSpacing: 1.2, color: colors.warning },
  text: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.textSecondary },
  code: {
    fontFamily: fonts.mono,
    fontSize: 12,
    color: colors.text,
    padding: spacing[2],
    borderRadius: radii.xs,
    backgroundColor: colors.background,
  },
  hint: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 18, color: colors.textTertiary },
  error: { fontFamily: fonts.ui, fontSize: 13, lineHeight: 19, color: colors.danger },
  add: { gap: spacing[2] },
});
