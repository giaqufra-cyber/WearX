import { colors, fonts, radii } from "@wearx/design-tokens";
import { ActivityIndicator, Image, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import type { DraftPhoto } from "@/features/create/draft";
import { MAX_PHOTOS } from "@/features/create/form";
import { IconBack, IconClose, IconPlus } from "@/ui/icons";

type Props = {
  photos: DraftPhoto[];
  onAdd: () => void;
  onRemove: (localId: string) => void;
  onMove: (localId: string, delta: -1 | 1) => void;
  onRetry: (localId: string) => void;
};

const STATUS_LABEL: Record<DraftPhoto["status"], string> = {
  queued: "In coda",
  preparing: "Preparo la foto",
  uploading: "Caricamento",
  processing: "Togliamo GPS e dati",
  ready: "Pronta",
  error: "Non caricata",
  rejected: "Non utilizzabile",
};

/** Le foto scelte, nell'ordine del carosello, con lo stato del caricamento di ognuna. */
export function PhotoStrip({ photos, onAdd, onRemove, onMove, onRetry }: Props) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.row}>
      {photos.map((photo, index) => {
        const busy = photo.status === "queued" || photo.status === "preparing" || photo.status === "uploading" || photo.status === "processing";
        const failed = photo.status === "error" || photo.status === "rejected";
        const label = `Foto ${index + 1} di ${photos.length}: ${STATUS_LABEL[photo.status]}${photo.message ? `. ${photo.message}` : ""}`;
        return (
          <View key={photo.localId} style={styles.tileWrap}>
            <View style={[styles.tile, failed ? styles.tileFailed : null]} aria-label={label}>
              <Image source={{ uri: photo.uri }} style={styles.image} resizeMode="cover" />
              <View style={styles.number}>
                <Text style={styles.numberText}>{index + 1}</Text>
              </View>
              {busy ? (
                <View style={styles.overlay}>
                  {photo.status === "uploading" ? null : <ActivityIndicator color={colors.text} size="small" />}
                  <Text style={styles.overlayText}>{STATUS_LABEL[photo.status]}</Text>
                  {photo.status === "uploading" ? (
                    <View style={styles.bar}>
                      <View style={[styles.barFill, { width: `${Math.round(photo.progress * 100)}%` }]} />
                    </View>
                  ) : null}
                </View>
              ) : null}
              {failed ? (
                <View style={[styles.overlay, styles.overlayFailed]}>
                  <Text style={styles.overlayText} numberOfLines={3}>
                    {photo.message ?? STATUS_LABEL[photo.status]}
                  </Text>
                  {photo.status === "error" ? (
                    <Pressable role="button" aria-label={`Riprova la foto ${index + 1}`} onPress={() => onRetry(photo.localId)} style={styles.retry}>
                      <Text style={styles.retryText}>Riprova</Text>
                    </Pressable>
                  ) : null}
                </View>
              ) : null}
              {/* Per ultimo: deve restare toccabile anche sopra l'avviso di errore. */}
              <Pressable
                role="button"
                aria-label={`Togli la foto ${index + 1}`}
                onPress={() => onRemove(photo.localId)}
                style={styles.remove}
                hitSlop={8}
              >
                <IconClose color={colors.text} size={14} />
              </Pressable>
            </View>
            <View style={styles.moves}>
              <Pressable
                role="button"
                aria-label={`Sposta la foto ${index + 1} prima`}
                aria-disabled={index === 0}
                disabled={index === 0}
                onPress={() => onMove(photo.localId, -1)}
                style={[styles.move, index === 0 ? styles.moveOff : null]}
              >
                <IconBack color={colors.textSecondary} size={16} />
              </Pressable>
              <Pressable
                role="button"
                aria-label={`Sposta la foto ${index + 1} dopo`}
                aria-disabled={index === photos.length - 1}
                disabled={index === photos.length - 1}
                onPress={() => onMove(photo.localId, 1)}
                style={[styles.move, styles.moveRight, index === photos.length - 1 ? styles.moveOff : null]}
              >
                <IconBack color={colors.textSecondary} size={16} />
              </Pressable>
            </View>
          </View>
        );
      })}
      {photos.length < MAX_PHOTOS ? (
        <Pressable
          role="button"
          aria-label={photos.length ? "Aggiungi altre foto" : "Scegli le foto dalla galleria"}
          onPress={onAdd}
          style={({ pressed }) => [styles.tile, styles.add, pressed ? styles.pressed : null]}
        >
          <IconPlus color={colors.textSecondary} />
          <Text style={styles.addText}>{photos.length ? "Aggiungi" : "Galleria"}</Text>
        </Pressable>
      ) : null}
    </ScrollView>
  );
}

const TILE_W = 104;
const TILE_H = 130;

const styles = StyleSheet.create({
  row: { gap: 8, paddingVertical: 2 },
  tileWrap: { gap: 6 },
  tile: {
    width: TILE_W,
    height: TILE_H,
    borderRadius: radii.sm,
    overflow: "hidden",
    backgroundColor: colors.surfaceRaised,
    borderWidth: 2,
    borderColor: "transparent",
  },
  tileFailed: { borderColor: colors.dangerStrong },
  image: { width: "100%", height: "100%" },
  number: {
    position: "absolute",
    left: 5,
    top: 5,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
  },
  numberText: { fontFamily: fonts.uiExtraBold, fontSize: 12, color: colors.onAccent },
  remove: {
    position: "absolute",
    right: 5,
    top: 5,
    width: 24,
    height: 24,
    borderRadius: 12,
    backgroundColor: "rgba(10,10,11,0.65)",
    alignItems: "center",
    justifyContent: "center",
  },
  overlay: {
    position: "absolute",
    left: 0,
    right: 0,
    bottom: 0,
    padding: 6,
    gap: 4,
    backgroundColor: "rgba(10,10,11,0.72)",
    alignItems: "center",
  },
  overlayFailed: { top: 0, justifyContent: "center", backgroundColor: "rgba(60,14,10,0.82)" },
  overlayText: { fontFamily: fonts.uiSemiBold, fontSize: 10, color: colors.text, textAlign: "center" },
  bar: { alignSelf: "stretch", height: 3, borderRadius: 2, backgroundColor: "rgba(242,239,233,0.25)" },
  barFill: { height: 3, borderRadius: 2, backgroundColor: colors.accent },
  retry: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radii.pill, backgroundColor: colors.inverse },
  retryText: { fontFamily: fonts.uiBold, fontSize: 11, color: colors.onInverse },
  moves: { flexDirection: "row", justifyContent: "space-between" },
  move: {
    width: 44,
    height: 28,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
  },
  moveRight: { transform: [{ scaleX: -1 }] },
  moveOff: { opacity: 0.3 },
  add: {
    alignItems: "center",
    justifyContent: "center",
    gap: 4,
    borderStyle: "dashed",
    borderColor: "#3A3A40",
    borderWidth: 1,
    backgroundColor: "transparent",
  },
  addText: { fontFamily: fonts.uiSemiBold, fontSize: 12, color: colors.textSecondary },
  pressed: { opacity: 0.7 },
});
