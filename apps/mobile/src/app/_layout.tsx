import {
  Archivo_400Regular,
  Archivo_500Medium,
  Archivo_600SemiBold,
  Archivo_700Bold,
  Archivo_800ExtraBold,
} from "@expo-google-fonts/archivo";
import {
  BodoniModa_400Regular,
  BodoniModa_500Medium,
  BodoniModa_700Bold,
} from "@expo-google-fonts/bodoni-moda";
import { JetBrainsMono_400Regular, JetBrainsMono_600SemiBold } from "@expo-google-fonts/jetbrains-mono";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { colors } from "@wearx/design-tokens";
import { useFonts } from "expo-font";
import { DarkTheme, Stack, ThemeProvider } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useEffect, useState } from "react";

import { AuthProvider, useAuth } from "@/features/auth/AuthProvider";
import type { AppRoute } from "@/features/auth/routing";
import { ToastProvider } from "@/ui/Toast";

void SplashScreen.preventAutoHideAsync();

/** Tema di navigazione scuro con i colori del brand (bordi, sfondi durante le transizioni). */
const navigationTheme = {
  ...DarkTheme,
  colors: {
    ...DarkTheme.colors,
    primary: colors.accent,
    background: colors.background,
    card: colors.background,
    text: colors.text,
    border: colors.borderSubtle,
    notification: colors.accent,
  },
};

export default function RootLayout() {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: { queries: { staleTime: 60_000, retry: 2 } },
      }),
  );
  const [fontsLoaded, fontError] = useFonts({
    Archivo_400Regular,
    Archivo_500Medium,
    Archivo_600SemiBold,
    Archivo_700Bold,
    Archivo_800ExtraBold,
    BodoniModa_400Regular,
    BodoniModa_500Medium,
    BodoniModa_700Bold,
    JetBrainsMono_400Regular,
    JetBrainsMono_600SemiBold,
    ArchivoExpanded_800: require("../../assets/fonts/ArchivoExpanded-800.ttf"),
    ArchivoExpanded_900: require("../../assets/fonts/ArchivoExpanded-900.ttf"),
  });

  // Se un font non carica si mostra comunque l'app con i font di sistema.
  const fontsReady = fontsLoaded || Boolean(fontError);

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider value={navigationTheme}>
        <ToastProvider>
          <StatusBar style="light" />
          <AuthProvider>{fontsReady ? <RootNavigator /> : null}</AuthProvider>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

type ShownRoute = Exclude<AppRoute, "loading">;

/**
 * Un solo gruppo di schermate è raggiungibile alla volta, in base allo stato di accesso.
 * Durante i caricamenti brevi (es. subito dopo l'accesso) resta visibile la schermata precedente;
 * al primo avvio resta lo splash finché non si sa dove andare.
 */
function RootNavigator() {
  const { route } = useAuth();
  const [shown, setShown] = useState<ShownRoute | null>(null);
  if (route !== "loading" && route !== shown) setShown(route);

  useEffect(() => {
    if (shown) void SplashScreen.hideAsync();
  }, [shown]);

  if (!shown) return null;

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }}>
      <Stack.Protected guard={shown === "app"}>
        <Stack.Screen name="(tabs)" />
      </Stack.Protected>
      <Stack.Protected guard={shown === "auth"}>
        <Stack.Screen name="(auth)" />
      </Stack.Protected>
      <Stack.Protected guard={shown === "onboarding"}>
        <Stack.Screen name="(onboarding)" />
      </Stack.Protected>
      <Stack.Protected guard={shown === "offline"}>
        <Stack.Screen name="offline" />
      </Stack.Protected>
      <Stack.Protected guard={shown === "suspended"}>
        <Stack.Screen name="suspended" />
      </Stack.Protected>
      <Stack.Protected guard={__DEV__}>
        <Stack.Screen name="dev/ui" />
      </Stack.Protected>
    </Stack>
  );
}
