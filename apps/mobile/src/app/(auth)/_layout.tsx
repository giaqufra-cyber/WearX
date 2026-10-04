import { colors } from "@wearx/design-tokens";
import { Stack } from "expo-router";

/** Gruppo raggiungibile solo senza sessione: benvenuto, registrazione, codice, accesso. */
export const unstable_settings = { initialRouteName: "welcome" };

export default function AuthLayout() {
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }}>
      <Stack.Screen name="welcome" />
      <Stack.Screen name="signup" />
      <Stack.Screen name="verify" />
      <Stack.Screen name="login" />
    </Stack>
  );
}
