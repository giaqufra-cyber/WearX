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

  useEffect(() => {
    // Se un font non carica si mostra comunque l'app con i font di sistema.
    if (fontsLoaded || fontError) {
      void SplashScreen.hideAsync();
    }
  }, [fontsLoaded, fontError]);

  if (!fontsLoaded && !fontError) {
    return null;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider value={navigationTheme}>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: colors.background },
          }}
        />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
