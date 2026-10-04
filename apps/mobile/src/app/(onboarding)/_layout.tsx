import { colors } from "@wearx/design-tokens";
import { Stack } from "expo-router";

/**
 * Gruppo raggiungibile con sessione ma senza profilo WearX:
 * verifica dell'età, tipo di profilo, stili (seduta 5).
 */
export const unstable_settings = { initialRouteName: "age" };

export default function OnboardingLayout() {
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: colors.background } }}>
      <Stack.Screen name="age" />
    </Stack>
  );
}
