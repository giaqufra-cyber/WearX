import type { Post } from "@wearx/api-types";
import { colors, fonts, radii } from "@wearx/design-tokens";
import { Image } from "expo-image";
import { useRef, useState } from "react";
import {
  FlatList,
  type NativeScrollEvent,
  type NativeSyntheticEvent,
  PixelRatio,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { bestVariant } from "@/features/feed/format";
import { IconTag } from "@/ui/icons";

type Props = { post: Post; width: number; authorLabel: string };

/** Carosello delle foto (prototipo): scorrimento, tocco a sinistra/destra, contatore, capi sulla foto. */
export function Carousel({ post, width, authorLabel }: Props) {
  const height = Math.round(width * 1.25); // 4:5, il formato verticale dei fit
  const [index, setIndex] = useState(0);
  const [tagsOpen, setTagsOpen] = useState(false);
  const list = useRef<FlatList<Post["media"][number]>>(null);
  const count = post.media.length;
  const pins = post.items.filter((i) => i.media_position === index && i.pin_x !== null && i.pin_y !== null);
  const tagged = post.items.filter((i) => i.pin_x !== null).length;

  const go = (next: number) => {
    const target = Math.min(count - 1, Math.max(0, next));
    if (target === index) return;
    setIndex(target);
    list.current?.scrollToOffset({ offset: target * width, animated: true });
  };

  const onScrollEnd = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    setIndex(Math.round(event.nativeEvent.contentOffset.x / width));
  };

  return (
    <View>
      <View style={{ width, height }}>
        <FlatList
          ref={list}
          data={post.media}
          horizontal
          pagingEnabled
          showsHorizontalScrollIndicator={false}
          keyExtractor={(m) => String(m.position)}
          onMomentumScrollEnd={onScrollEnd}
          getItemLayout={(_d, i) => ({ length: width, offset: width * i, index: i })}
          renderItem={({ item, index: i }) => (
            <Image
              source={bestVariant(item.urls.variants, width * PixelRatio.get())}
              placeholder={{ blurhash: item.blurhash }}
              contentFit="cover"
              transition={180}
              recyclingKey={`${post.id}-${item.position}`}
              accessibilityLabel={`Foto ${i + 1} di ${count} del fit di ${authorLabel}`}
              style={{ width, height }}
            />
          )}
        />
        <View pointerEvents="none" style={[styles.corner, styles.cornerTL]} />
        <View pointerEvents="none" style={[styles.corner, styles.cornerBR]} />
        {count > 1 ? (
          <>
            <Pressable role="button" aria-label="Foto precedente" onPress={() => go(index - 1)} style={[styles.zone, styles.zoneLeft]} />
            <Pressable role="button" aria-label="Foto successiva" onPress={() => go(index + 1)} style={[styles.zone, styles.zoneRight]} />
            <View pointerEvents="none" style={styles.counter}>
              <Text style={styles.counterText}>
                {index + 1}/{count}
              </Text>
            </View>
          </>
        ) : null}
        {tagsOpen
          ? pins.map((pin) => (
              <View
                key={pin.position}
                pointerEvents="none"
                style={[styles.pin, { left: (pin.pin_x ?? 0) * width - 6, top: (pin.pin_y ?? 0) * height - 6 }]}
              >
                <View style={styles.pinDot} />
                <Text style={styles.pinLabel} numberOfLines={1}>
                  {pin.brand}
                </Text>
              </View>
            ))
          : null}
        {tagged > 0 ? (
          <Pressable
            role="button"
            aria-label={tagsOpen ? "Nascondi i capi sulla foto" : "Mostra i capi sulla foto"}
            aria-expanded={tagsOpen}
            onPress={() => setTagsOpen((open) => !open)}
            style={styles.tagsButton}
          >
            <IconTag color={colors.text} size={14} />
            <Text style={styles.tagsText}>{tagsOpen ? "Nascondi" : `Capi · ${tagged}`}</Text>
          </Pressable>
        ) : null}
      </View>
      {count > 1 ? (
        <View style={styles.dots} aria-hidden>
          {post.media.map((m, i) => (
            <View key={m.position} style={[styles.dot, i === index ? styles.dotOn : null]} />
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  corner: { position: "absolute", width: 22, height: 22, borderColor: "rgba(242,239,233,0.5)" },
  cornerTL: { left: 16, top: 16, borderLeftWidth: 1.5, borderTopWidth: 1.5 },
  cornerBR: { right: 16, bottom: 16, borderRightWidth: 1.5, borderBottomWidth: 1.5 },
  zone: { position: "absolute", top: 0, bottom: 56, width: "30%" },
  zoneLeft: { left: 0 },
  zoneRight: { right: 0 },
  counter: {
    position: "absolute",
    right: 14,
    top: 14,
    backgroundColor: "rgba(10,10,11,0.7)",
    borderRadius: radii.pill,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  counterText: { fontFamily: fonts.mono, fontSize: 11, color: colors.text },
  pin: { position: "absolute", flexDirection: "row", alignItems: "center", gap: 6 },
  pinDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: colors.accent,
    borderWidth: 3,
    borderColor: "rgba(10,10,11,0.55)",
  },
  pinLabel: {
    backgroundColor: colors.background,
    color: colors.text,
    fontFamily: fonts.uiBold,
    fontSize: 11,
    letterSpacing: 0.6,
    textTransform: "uppercase",
    paddingHorizontal: 9,
    paddingVertical: 6,
    borderRadius: 7,
    overflow: "hidden",
    maxWidth: 160,
  },
  tagsButton: {
    position: "absolute",
    left: 12,
    bottom: 12,
    height: 36,
    paddingHorizontal: 13,
    borderRadius: radii.pill,
    backgroundColor: "rgba(10,10,11,0.75)",
    flexDirection: "row",
    alignItems: "center",
    gap: 7,
  },
  tagsText: { fontFamily: fonts.uiSemiBold, fontSize: 12, color: colors.text },
  dots: { flexDirection: "row", justifyContent: "center", gap: 5, paddingTop: 10 },
  dot: { width: 6, height: 6, borderRadius: 3, backgroundColor: "#3A3A40" },
  dotOn: { width: 18, backgroundColor: colors.text },
});
