import { colors, fonts, radii, spacing } from "@wearx/design-tokens";
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Animated, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { IconCheck } from "@/ui/icons";

type Tone = "success" | "error";
type ToastState = { id: number; message: string; tone: Tone } | null;
type ToastApi = { show: (message: string, options?: { tone?: Tone; durationMs?: number }) => void };

const ToastContext = createContext<ToastApi | null>(null);

export const TOAST_DURATION_MS = 2400;

/** Avvisi brevi in alto (es. "Hai votato 84. Il voto è anonimo."). Uno alla volta. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const counter = useRef(0);

  const show = useCallback<ToastApi["show"]>((message, options) => {
    if (timer.current) clearTimeout(timer.current);
    counter.current += 1;
    setToast({ id: counter.current, message, tone: options?.tone ?? "success" });
    timer.current = setTimeout(() => setToast(null), options?.durationMs ?? TOAST_DURATION_MS);
  }, []);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const api = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      {/* Contenitore sempre presente (e mai "appiattito" da React Native): l'avviso nasce qui
          dentro, non come nuova vista accanto alle schermate che cambiano. */}
      <View pointerEvents="box-none" collapsable={false} style={StyleSheet.absoluteFill}>
        {toast ? <ToastView key={toast.id} message={toast.message} tone={toast.tone} /> : null}
      </View>
    </ToastContext.Provider>
  );
}

function ToastView({ message, tone }: { message: string; tone: Tone }) {
  const insets = useSafeAreaInsets();
  const opacity = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    Animated.timing(opacity, { toValue: 1, duration: 160, useNativeDriver: true }).start();
  }, [opacity]);
  return (
    <Animated.View
      pointerEvents="none"
      style={[styles.toast, { top: insets.top + spacing[3], opacity }, tone === "error" ? styles.error : null]}
    >
      <View accessible role="alert" aria-live="polite" style={styles.row}>
        {tone === "success" ? <IconCheck color={colors.onInverse} size={18} /> : null}
        <Text style={[styles.text, tone === "error" ? styles.errorText : null]}>{message}</Text>
      </View>
    </Animated.View>
  );
}

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast va usato dentro <ToastProvider>");
  return api;
}

const styles = StyleSheet.create({
  toast: {
    position: "absolute",
    left: spacing[4],
    right: spacing[4],
    zIndex: 100,
    backgroundColor: colors.inverse,
    borderRadius: radii.md,
    paddingVertical: 13,
    paddingHorizontal: 14,
    shadowColor: "#000",
    shadowOpacity: 0.45,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 12 },
    elevation: 8,
  },
  error: { backgroundColor: "#3A1612", borderWidth: 1, borderColor: colors.dangerStrong },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  text: { flex: 1, fontFamily: fonts.uiSemiBold, fontSize: 13, lineHeight: 18, color: colors.onInverse },
  errorText: { color: colors.text },
});
