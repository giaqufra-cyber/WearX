import { colors, fonts, minTouchTarget, radii } from "@wearx/design-tokens";
import { Tabs } from "expo-router";
import { StyleSheet, View } from "react-native";

import { IconPlus, IconSearch, IconStyles, IconUser } from "@/ui/icons";

/** Barra in basso come nel prototipo: Stili, Cerca, + (nuovo fit), Account. */
export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        sceneStyle: { backgroundColor: colors.background },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textTertiary,
        tabBarStyle: styles.bar,
        tabBarLabelStyle: styles.label,
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: "STILI",
          tabBarAccessibilityLabel: "Feed dei tuoi stili",
          tabBarIcon: ({ color }) => <IconStyles color={color} />,
        }}
      />
      <Tabs.Screen
        name="explore"
        options={{
          title: "CERCA",
          tabBarAccessibilityLabel: "Esplora per stile",
          tabBarIcon: ({ color }) => <IconSearch color={color} />,
        }}
      />
      <Tabs.Screen
        name="create"
        options={{
          title: "",
          tabBarAccessibilityLabel: "Pubblica un fit",
          tabBarIcon: ({ focused }) => (
            <View style={[styles.create, focused && styles.createFocused]}>
              <IconPlus color={colors.onAccent} />
            </View>
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "ACCOUNT",
          tabBarAccessibilityLabel: "Il tuo profilo",
          tabBarIcon: ({ color }) => <IconUser color={color} />,
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  bar: {
    backgroundColor: colors.background,
    borderTopColor: colors.borderSubtle,
    borderTopWidth: 1,
    minHeight: 78,
    elevation: 0,
    shadowOpacity: 0,
    boxShadow: "none",
  },
  label: { fontFamily: fonts.uiBold, fontSize: 10, letterSpacing: 1 },
  create: {
    width: 56,
    height: minTouchTarget,
    borderRadius: radii.md,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 10,
  },
  createFocused: { backgroundColor: colors.inverse },
});
