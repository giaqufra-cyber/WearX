import { colors, fonts } from "@wearx/design-tokens";
import * as WebBrowser from "expo-web-browser";
import { Fragment } from "react";
import { StyleSheet, Text, type TextStyle } from "react-native";

import { useAppConfig } from "@/features/styles/useAppConfig";
import { apiUrl } from "@/lib/api";

export type LegalDoc = "terms" | "privacy" | "community_rules" | "feed_explainer";

export const LEGAL_TITLES: Record<LegalDoc, string> = {
  terms: "Termini di servizio",
  privacy: "Informativa privacy",
  community_rules: "Regole della community",
  feed_explainer: "Come funziona il feed",
};

const FALLBACK_PATH: Record<LegalDoc, string> = {
  terms: "termini",
  privacy: "privacy",
  community_rules: "regole",
  feed_explainer: "come-funziona-il-feed",
};

/** Indirizzi delle pagine legali: da /v1/config, oppure quelli dell'API se la config non c'è ancora. */
export function useLegalLinks(): Record<LegalDoc, string> {
  const legal = useAppConfig().data?.legal;
  const fallback = (doc: LegalDoc) => `${apiUrl()}/legal/${FALLBACK_PATH[doc]}`;
  return {
    terms: legal?.terms ?? fallback("terms"),
    privacy: legal?.privacy ?? fallback("privacy"),
    community_rules: legal?.community_rules ?? fallback("community_rules"),
    feed_explainer: legal?.feed_explainer ?? fallback("feed_explainer"),
  };
}

export function openLegal(url: string): void {
  void WebBrowser.openBrowserAsync(url);
}

/** Link dentro un testo: "Termini di servizio" che apre la pagina (ruolo "link"). */
export function LegalLink({ doc, label, style }: { doc: LegalDoc; label?: string; style?: TextStyle }) {
  const links = useLegalLinks();
  return (
    <Text role="link" onPress={() => openLegal(links[doc])} style={[styles.link, style]}>
      {label ?? LEGAL_TITLES[doc]}
    </Text>
  );
}

/** Riga di link separati da "·" (es. sotto le caselle di consenso). */
export function LegalLinkRow({ docs, style }: { docs: LegalDoc[]; style?: TextStyle }) {
  return (
    <Text style={[styles.row, style]}>
      {docs.map((doc, i) => (
        <Fragment key={doc}>
          {i > 0 ? " · " : null}
          <LegalLink doc={doc} />
        </Fragment>
      ))}
    </Text>
  );
}

const styles = StyleSheet.create({
  link: { color: colors.text, textDecorationLine: "underline" },
  row: { fontFamily: fonts.ui, fontSize: 12, lineHeight: 18, color: colors.textTertiary },
});
