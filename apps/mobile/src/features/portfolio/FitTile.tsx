import type { PortfolioTile } from "@wearx/api-types";
import { colors, fonts, radii } from "@wearx/design-tokens";
import { Image } from "expo-image";
import { memo } from "react";
import { PixelRatio, Pressable, StyleSheet, Text, View } from "react-native";

import { bestVariant } from "@/features/feed/format";
import { positionLabel, tileScore, tileStatus } from "@/features/portfolio/format";
import { IconChevronLeft, IconChevronRight } from "@/ui/icons";

type Props = {
  tile: PortfolioTile;
  index: number;
  width: number;
  isCover: boolean;
  own: boolean;
  editing: boolean;
  canPrev: boolean;
  canNext: boolean;
  onOpen: (tile: PortfolioTile) => void;
  onPrev: (tile: PortfolioTile, index: number) => void;
  onNext: (tile: PortfolioTile, index: number) => void;
  /** Numero "01", "02"… in alto: ha senso nel portfolio (ordine scelto), non in uno stile. */
  numbered?: boolean;
  /** Nome dello stile sopra il titolo: inutile nella pagina dello stile stesso. */
  showStyle?: boolean;
};

const RATIO = 1.28; // 175 x 224 come nel prototipo
// Sfumature fatte di strisce sottili (curva morbida: niente bande visibili). In basso fino al
// quasi nero per leggere titolo e voto; in alto leggera, per la posizione e i badge.
const shade = (steps: number, max: number) =>
  Array.from({ length: steps }, (_, i) => Math.round(max * ((i + 1) / steps) ** 1.6 * 1000) / 1000);
const SHADE = shade(28, 0.88);
const SHADE_TOP = shade(8, 0.35).reverse();

/** Fit nella griglia del portfolio: foto, posizione, copertina, stile, titolo, voto. */
export const FitTile = memo(function FitTile({
  tile,
  index,
  width,
  isCover,
  own,
  editing,
  canPrev,
  canNext,
  onOpen,
  onPrev,
  onNext,
  numbered = true,
  showStyle = true,
}: Props) {
  const height = Math.round(width * RATIO);
  const url = tile.photo ? bestVariant(tile.photo.urls.variants, width * PixelRatio.get()) : undefined;
  const { score, sub } = tileScore(tile, own);
  const status = own ? tileStatus(tile) : null;
  // Senza didascalia niente titolo: prima ripeteva il nome dello stile due volte.
  const title = tile.caption;
  const label = [
    numbered ? `Fit ${index + 1}` : "Fit",
    isCover ? "copertina" : null,
    tile.style.name,
    tile.caption,
    tile.average !== null ? `media ${Math.round(tile.average)}` : null,
    status?.toLowerCase(),
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <View style={[styles.tile, { width, height, backgroundColor: tile.style.tone }]}>
      <Pressable
        role="button"
        aria-label={label}
        disabled={editing}
        onPress={() => onOpen(tile)}
        style={StyleSheet.absoluteFill}
      >
        {url ? (
          <Image
            source={{ uri: url }}
            placeholder={tile.photo ? { blurhash: tile.photo.blurhash } : undefined}
            contentFit="cover"
            transition={150}
            style={StyleSheet.absoluteFill}
            accessibilityIgnoresInvertColors
            // Decorativa: il pulsante intorno ha già la descrizione.
            accessibilityLabel=""
            accessible={false}
          />
        ) : null}
        {/* Sfumatura in basso per leggere il testo sopra la foto. */}
        <View style={styles.shadeTop} pointerEvents="none">
          {SHADE_TOP.map((opacity) => (
            <View key={opacity} style={[styles.band, { opacity }]} />
          ))}
        </View>
        <View style={[styles.shade, { height: height * 0.62 }]} pointerEvents="none">
          {SHADE.map((opacity) => (
            <View key={opacity} style={[styles.band, { opacity }]} />
          ))}
        </View>

        {numbered ? <Text style={styles.pos}>{positionLabel(index)}</Text> : null}
        <View style={styles.badges}>
          {isCover ? <Text style={[styles.badge, styles.cover]}>COPERTINA</Text> : null}
          {status ? <Text style={[styles.badge, styles.status]}>{status}</Text> : null}
        </View>
        {tile.media_count > 1 ? <Text style={styles.count}>1/{tile.media_count}</Text> : null}

        <View style={styles.bottom}>
          {showStyle ? (
            <Text style={styles.style} numberOfLines={1}>
              {tile.style.name}
            </Text>
          ) : null}
          {title ? (
            <Text style={styles.title} numberOfLines={1}>
              {title}
            </Text>
          ) : null}
          <View style={styles.scoreRow}>
            <Text style={styles.score}>{score}</Text>
            <Text style={styles.sub} numberOfLines={1}>
              {sub}
            </Text>
          </View>
        </View>
      </Pressable>

      {editing ? (
        <View style={styles.edit}>
          <Pressable
            role="button"
            aria-label={`Sposta prima: fit ${index + 1}`}
            aria-disabled={!canPrev}
            disabled={!canPrev}
            onPress={() => onPrev(tile, index)}
            style={[styles.arrow, !canPrev && styles.arrowOff]}
            hitSlop={4}
          >
            <IconChevronLeft color={colors.onInverse} />
          </Pressable>
          <Pressable
            role="button"
            aria-label={`Sposta dopo: fit ${index + 1}`}
            aria-disabled={!canNext}
            disabled={!canNext}
            onPress={() => onNext(tile, index)}
            style={[styles.arrow, !canNext && styles.arrowOff]}
            hitSlop={4}
          >
            <IconChevronRight color={colors.onInverse} />
          </Pressable>
        </View>
      ) : null}
    </View>
  );
});

const styles = StyleSheet.create({
  tile: { borderRadius: radii.lg, overflow: "hidden" },
  shadeTop: { position: "absolute", left: 0, right: 0, top: 0, height: 56 },
  shade: { position: "absolute", left: 0, right: 0, bottom: 0 },
  band: { flex: 1, backgroundColor: "#0A0A0B" },
  pos: {
    position: "absolute",
    left: 12,
    top: 12,
    fontFamily: fonts.mono,
    fontSize: 10,
    letterSpacing: 1.4,
    color: "rgba(242,239,233,0.8)",
  },
  badges: { position: "absolute", right: 10, top: 10, alignItems: "flex-end", gap: 4 },
  badge: {
    fontFamily: fonts.uiExtraBold,
    fontSize: 9,
    letterSpacing: 1.1,
    paddingHorizontal: 7,
    paddingVertical: 4,
    borderRadius: 5,
    overflow: "hidden",
  },
  cover: { backgroundColor: colors.accent, color: colors.onAccent },
  status: { backgroundColor: colors.warning, color: colors.onAccent },
  count: {
    position: "absolute",
    right: 12,
    bottom: 14,
    fontFamily: fonts.mono,
    fontSize: 10,
    color: "rgba(242,239,233,0.7)",
  },
  bottom: { position: "absolute", left: 12, right: 12, bottom: 12 },
  style: { fontFamily: fonts.display, fontSize: 14, color: "rgba(242,239,233,0.8)" },
  title: { fontFamily: fonts.uiBold, fontSize: 14, color: colors.text, marginTop: 2 },
  scoreRow: { flexDirection: "row", alignItems: "baseline", gap: 6, marginTop: 6, paddingRight: 28 },
  score: {
    fontFamily: fonts.numeric,
    fontSize: 32,
    lineHeight: 32,
    color: colors.text,
    fontVariant: ["tabular-nums"],
  },
  sub: { fontFamily: fonts.ui, fontSize: 11, color: "rgba(242,239,233,0.75)", flexShrink: 1 },
  edit: {
    ...StyleSheet.absoluteFill,
    backgroundColor: "rgba(10,10,11,0.5)",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 14,
  },
  arrow: {
    width: 46,
    height: 46,
    borderRadius: 23,
    backgroundColor: colors.inverse,
    alignItems: "center",
    justifyContent: "center",
  },
  arrowOff: { opacity: 0.3 },
});
