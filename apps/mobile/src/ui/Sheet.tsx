import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import type { ReactNode } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { IconButton } from "@/ui/IconButton";
import { IconClose } from "@/ui/icons";

type Props = {
  visible: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
};

/** Pannello dal basso (segnala, opzioni del fit, conferme). Chiude con lo sfondo o con la X. */
export function Sheet({ visible, title, onClose, children }: Props) {
  const insets = useSafeAreaInsets();
  return (
    <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <View style={styles.root}>
        <Pressable style={styles.backdrop} onPress={onClose} role="button" aria-label="Chiudi" />
        <View
          style={[styles.panel, { paddingBottom: insets.bottom + spacing[5] }]}
          aria-modal
          role="dialog"
          aria-label={title}
        >
          <View style={styles.handle} />
          <View style={styles.header}>
            <Text role="heading" style={styles.title}>
              {title}
            </Text>
            <IconButton label="Chiudi" onPress={onClose}>
              <IconClose color={colors.text} />
            </IconButton>
          </View>
          {children}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, justifyContent: "flex-end" },
  backdrop: { ...StyleSheet.absoluteFill, backgroundColor: "rgba(0,0,0,0.6)" },
  panel: {
    backgroundColor: colors.surface,
    borderTopLeftRadius: radii.xl,
    borderTopRightRadius: radii.xl,
    paddingHorizontal: spacing[5],
    paddingTop: spacing[2],
    gap: spacing[3],
  },
  handle: { alignSelf: "center", width: 40, height: 4, borderRadius: 2, backgroundColor: "#3A3A40" },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { fontFamily: fonts.display, fontSize: 24, color: colors.text, flex: 1 },
});
