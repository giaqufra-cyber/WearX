import type { Avatar as AvatarData } from "@wearx/api-types";
import { colors, fonts } from "@wearx/design-tokens";
import { Image } from "expo-image";
import { PixelRatio, StyleSheet, Text, View } from "react-native";

import { bestVariant, initials } from "@/features/feed/format";

// Fondi per le iniziali: scelti dal nickname (sempre lo stesso colore per la stessa persona).
// Prima il colore veniva dal primo stile della persona, che ora non è più pubblico (seduta 27).
const TONES = ["#2F3A2B", "#3A1418", "#1E2A3A", "#3A2E14", "#2B1E3A", "#143A33", "#3A1E2E", "#2A2A2E"];

export function toneFor(nickname: string): string {
  let hash = 0;
  for (let i = 0; i < nickname.length; i++) hash = (hash * 31 + nickname.charCodeAt(i)) >>> 0;
  return TONES[hash % TONES.length]!;
}

type Props = {
  nickname: string;
  avatar?: AvatarData | null;
  size: number;
  /** Foto scelta ma non ancora salvata (anteprima locale). */
  localUri?: string | null;
};

/** Foto profilo rotonda, oppure le iniziali su un fondo colorato. Decorativa per i lettori di schermo. */
export function Avatar({ nickname, avatar, size, localUri }: Props) {
  const url = localUri ?? (avatar ? bestVariant(avatar.urls.variants, size * PixelRatio.get()) : undefined);
  const round = { width: size, height: size, borderRadius: size / 2 };
  return (
    <View style={[styles.base, round, { backgroundColor: toneFor(nickname) }]} aria-hidden>
      {url ? (
        <Image
          source={{ uri: url }}
          placeholder={avatar ? { blurhash: avatar.blurhash } : undefined}
          contentFit="cover"
          transition={120}
          style={round}
          accessible={false}
          testID="avatar-photo"
        />
      ) : (
        <Text style={[styles.initials, { fontSize: Math.max(11, Math.round(size * 0.3)) }]}>{initials(nickname)}</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  base: { alignItems: "center", justifyContent: "center", overflow: "hidden" },
  initials: { fontFamily: fonts.uiExtraBold, color: colors.text },
});
