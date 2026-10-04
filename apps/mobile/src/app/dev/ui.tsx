/**
 * Catalogo del design system, per controllare i componenti accanto al prototipo.
 * Esiste solo in sviluppo: nelle build di produzione rimanda alla home.
 */
import { colors, spacing } from "@wearx/design-tokens";
import { Redirect } from "expo-router";
import { useState } from "react";
import { ScrollView, StyleSheet, View } from "react-native";

import {
  Badge,
  Button,
  Checkbox,
  Chip,
  EmptyState,
  PasswordStrength,
  Screen,
  SegmentedControl,
  Sheet,
  Skeleton,
  StyleTile,
  Text,
  TextField,
  Toggle,
  useToast,
} from "@/ui";

export default function UiCatalog() {
  const toast = useToast();
  const [nick, setNick] = useState("nico.atelier");
  const [pw, setPw] = useState("Archivio26!");
  const [mode, setMode] = useState<"email" | "phone">("email");
  const [account, setAccount] = useState<"private" | "business">("private");
  const [hidePrices, setHidePrices] = useState(true);
  const [twoFa, setTwoFa] = useState(false);
  const [terms, setTerms] = useState(true);
  const [chip, setChip] = useState("all");
  const [picked, setPicked] = useState<string[]>(["old-money"]);
  const [sheet, setSheet] = useState(false);

  if (!__DEV__) return <Redirect href="/" />;

  const togglePick = (slug: string) =>
    setPicked((p) => (p.includes(slug) ? p.filter((s) => s !== slug) : [...p, slug]));

  return (
    <Screen>
      <Text variant="display" role="heading" style={styles.title}>
        Design system
      </Text>

      <Section title="Pulsanti">
        <Button label="Crea il tuo account" onPress={() => toast.show("Pulsante principale premuto.")} fullWidth />
        <Button label="Ho già un account" variant="secondary" onPress={() => undefined} fullWidth />
        <View style={styles.row}>
          <Button label="Vota" variant="inverse" size="md" onPress={() => toast.show("Hai votato 84. Il voto è anonimo.")} />
          <Button label="Pubblica" size="sm" onPress={() => undefined} />
          <Button label="Continua" size="md" disabled onPress={() => undefined} />
          <Button label="Invio" size="md" loading onPress={() => undefined} />
        </View>
        <Button label="Elimina account" variant="danger" onPress={() => toast.show("Serve la password.", { tone: "error" })} />
      </Section>

      <Section title="Campi">
        <TextField
          label="Nickname"
          prefix="@"
          value={nick}
          onChangeText={setNick}
          autoCapitalize="none"
          hint="@nico.atelier è libero"
          hintColor={colors.accent}
        />
        <SegmentedControl
          label="Tipo di contatto"
          size="sm"
          value={mode}
          onChange={setMode}
          options={[
            { value: "email", label: "Email" },
            { value: "phone", label: "Telefono" },
          ]}
        />
        <TextField label="Email" value="nome@" onChangeText={() => undefined} error="Controlla l'indirizzo email." />
        <TextField label="Password" secure value={pw} onChangeText={setPw} />
        <PasswordStrength password={pw} />
      </Section>

      <Section title="Scelte">
        <SegmentedControl
          label="Tipo di profilo"
          value={account}
          onChange={setAccount}
          options={[
            { value: "private", label: "Privato" },
            { value: "business", label: "Business" },
          ]}
        />
        <Toggle
          label="Nascondi i prezzi"
          description="I capi restano taggati, il prezzo non si vede."
          value={hidePrices}
          onValueChange={setHidePrices}
        />
        <Toggle label="Verifica in due passaggi" description="Codice da app a ogni nuovo accesso." value={twoFa} onValueChange={setTwoFa} />
        <Checkbox label="Accetto le regole della community: si vota, non si insulta." checked={terms} onChange={setTerms} />
      </Section>

      <Section title="Chip e badge">
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
          {[
            ["all", "Tutti"],
            ["old-money", "Old Money"],
            ["jappo", "Jappo"],
            ["gala", "Galà"],
          ].map(([slug, name]) => (
            <Chip key={slug} label={name!} selected={chip === slug} onPress={() => setChip(slug!)} />
          ))}
        </ScrollView>
        <View style={styles.row}>
          <Chip label="Old Money" variant="style" tone="#2F3A2B" />
          <Chip label="Minimal" variant="style" tone="#4E4A45" />
          <Badge label="Stagionale" />
          <Badge label="Copertina" tone="inverse" />
          <Badge label="Privato" tone="outline" />
        </View>
      </Section>

      <Section title="Stili">
        <View style={styles.grid}>
          <StyleTile name="Old Money" tagline="Quiet luxury, cachemire" tone="#2F3A2B" selectable
            selected={picked.includes("old-money")} onPress={() => togglePick("old-money")} />
          <StyleTile name="Jappo" tagline="Tokyo street, layering" tone="#1F2946" selectable
            selected={picked.includes("jappo")} onPress={() => togglePick("jappo")} />
        </View>
        <View style={styles.grid}>
          <StyleTile name="Halloween" tagline="Costumi, dark, cosplay" tone="#3E1F06" badge="Stagionale"
            meta="15,1K MEMBRI" height={150} onPress={() => undefined} />
          <StyleTile name="Beach Party" tagline="Lino, costumi" tone="#0E4A57" badge="18+"
            meta="27,9K MEMBRI" height={150} onPress={() => undefined} />
        </View>
      </Section>

      <Section title="Caricamento e stati vuoti">
        <Skeleton height={220} radius={16} />
        <View style={styles.row}>
          <Skeleton width={120} height={14} radius={7} />
          <Skeleton width={60} height={14} radius={7} />
        </View>
        <EmptyState
          title="Ancora nessun fit qui"
          body="Sii il primo a pubblicarne uno in questo stile."
          action={{ label: "Apri il pannello", onPress: () => setSheet(true) }}
        />
      </Section>

      <Sheet visible={sheet} title="Segnala il fit" onClose={() => setSheet(false)}>
        <Button label="Nudità o contenuti sessuali" variant="secondary" fullWidth onPress={() => setSheet(false)} />
        <Button label="Molestie o insulti" variant="secondary" fullWidth onPress={() => setSheet(false)} />
        <Button label="Stile sbagliato" variant="secondary" fullWidth onPress={() => setSheet(false)} />
      </Sheet>
    </Screen>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <View style={styles.section}>
      <Text variant="label">{title}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  title: { paddingTop: spacing[3] },
  section: { gap: spacing[3], paddingTop: spacing[4], borderTopWidth: 1, borderTopColor: colors.divider },
  row: { flexDirection: "row", flexWrap: "wrap", gap: spacing[2], alignItems: "center" },
  grid: { flexDirection: "row", gap: spacing[2] },
});
