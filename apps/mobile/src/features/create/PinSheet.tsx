import { colors, fonts, spacing } from "@wearx/design-tokens";
import { useEffect, useState } from "react";
import { Image, type GestureResponderEvent, Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from "react-native";

import type { DraftPhoto } from "@/features/create/draft";
import { type ItemPin, roundPin } from "@/features/create/form";
import { Button } from "@/ui/Button";
import { Sheet } from "@/ui/Sheet";

type Props = {
  visible: boolean;
  /** "Capo 2", o brand e nome se già scritti. */
  itemLabel: string;
  photos: Pick<DraftPhoto, "localId" | "uri" | "width" | "height">[];
  pin: ItemPin | null | undefined;
  onSave: (pin: ItemPin | null) => void;
  onClose: () => void;
};

const MARKER = 22;

/** Punto toccato dentro la foto, in 0-1 (su telefono locationX/Y, sul web offsetX/Y). */
export function pointFromEvent(event: GestureResponderEvent, width: number, height: number): { x: number; y: number } | null {
  const native = event.nativeEvent as unknown as Partial<Record<"locationX" | "locationY" | "offsetX" | "offsetY", number>>;
  const px = native.locationX ?? native.offsetX;
  const py = native.locationY ?? native.offsetY;
  if (px === undefined || py === undefined || !width || !height) return null;
  return { x: roundPin(px / width), y: roundPin(py / height) };
}

/**
 * "Segna sulla foto": scegli in quale foto si vede il capo e tocca il punto.
 * Il punto compare sul fit pubblicato con il nome del brand.
 */
export function PinSheet({ visible, itemLabel, photos, pin, onSave, onClose }: Props) {
  const { width: screenW, height: screenH } = useWindowDimensions();
  const startPhoto = photos.some((p) => p.localId === pin?.photo) ? pin!.photo : (photos[0]?.localId ?? "");
  const [photoId, setPhotoId] = useState(startPhoto);
  const [point, setPoint] = useState<{ x: number; y: number } | null>(pin && pin.photo === startPhoto ? pin : null);

  useEffect(() => {
    if (!visible) return;
    setPhotoId(startPhoto);
    setPoint(pin && pin.photo === startPhoto ? { x: pin.x, y: pin.y } : null);
    // Ogni apertura riparte dal punto salvato.
  }, [visible]);

  const index = Math.max(0, photos.findIndex((p) => p.localId === photoId));
  const photo = photos[index];
  const aspect = photo && photo.width > 0 && photo.height > 0 ? photo.width / photo.height : 3 / 4;
  const maxW = Math.min(screenW - 2 * spacing[5], 520);
  const maxH = Math.max(220, screenH * 0.5);
  const boxW = Math.round(Math.min(maxW, maxH * aspect));
  const boxH = Math.round(boxW / aspect);

  const choose = (localId: string) => {
    if (localId === photoId) return;
    setPhotoId(localId);
    setPoint(null);
  };

  return (
    <Sheet visible={visible} title={`Dove si vede: ${itemLabel}`} onClose={onClose}>
      {photos.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.thumbs}>
          {photos.map((p, i) => {
            const selected = p.localId === photoId;
            return (
              <Pressable
                key={p.localId}
                role="radio"
                aria-checked={selected}
                aria-label={`Foto ${i + 1}`}
                onPress={() => choose(p.localId)}
                style={[styles.thumb, selected ? styles.thumbSelected : null]}
              >
                <Image source={{ uri: p.uri }} style={styles.thumbImage} resizeMode="cover" />
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}

      {photo ? (
        <Pressable
          role="button"
          aria-label={`Foto ${index + 1}: tocca il punto dove si vede il capo`}
          onPress={(event) => {
            const next = pointFromEvent(event, boxW, boxH);
            if (next) setPoint(next);
          }}
          style={[styles.box, { width: boxW, height: boxH }]}
          testID="pin-photo"
        >
          <Image source={{ uri: photo.uri }} style={styles.full} resizeMode="cover" />
          {point ? (
            <View
              pointerEvents="none"
              style={[styles.marker, { left: point.x * boxW - MARKER / 2, top: point.y * boxH - MARKER / 2 }]}
            >
              <View style={styles.markerDot} />
            </View>
          ) : null}
        </Pressable>
      ) : null}

      <Text style={styles.note} aria-live="polite">
        {point ? "Punto segnato. Tocca ancora per spostarlo." : "Tocca la foto nel punto in cui si vede il capo."}
      </Text>

      <View style={styles.actions}>
        {pin ? (
          <View style={styles.action}>
            <Button
              label="Togli il punto"
              variant="secondary"
              size="md"
              fullWidth
              onPress={() => {
                onSave(null);
                onClose();
              }}
            />
          </View>
        ) : null}
        <View style={styles.action}>
          <Button
            label="Fatto"
            size="md"
            fullWidth
            disabled={!point || !photo}
            hint={point ? undefined : "Prima tocca un punto della foto"}
            onPress={() => {
              if (!point || !photo) return;
              onSave({ photo: photo.localId, x: point.x, y: point.y });
              onClose();
            }}
          />
        </View>
      </View>
    </Sheet>
  );
}

const styles = StyleSheet.create({
  thumbs: { gap: spacing[2], paddingBottom: spacing[3] },
  thumb: { width: 52, height: 64, borderRadius: 10, overflow: "hidden", borderWidth: 2, borderColor: "transparent" },
  thumbSelected: { borderColor: colors.text },
  thumbImage: { width: "100%", height: "100%" },
  box: { alignSelf: "center", borderRadius: 14, overflow: "hidden", backgroundColor: colors.surfaceRaised },
  full: { width: "100%", height: "100%", pointerEvents: "none" },
  marker: {
    position: "absolute",
    width: MARKER,
    height: MARKER,
    borderRadius: MARKER / 2,
    backgroundColor: "rgba(0,0,0,0.45)",
    borderWidth: 2,
    borderColor: "#FFFFFF",
    alignItems: "center",
    justifyContent: "center",
  },
  markerDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: "#FFFFFF" },
  note: {
    fontFamily: fonts.ui,
    fontSize: 13,
    lineHeight: 18,
    color: colors.textSecondary,
    textAlign: "center",
    marginTop: spacing[3],
  },
  actions: { flexDirection: "row", gap: spacing[2], marginTop: spacing[4] },
  action: { flex: 1 },
});
