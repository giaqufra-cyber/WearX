import { useLocalSearchParams } from "expo-router";
import { useEffect } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { PortfolioScreen } from "@/features/portfolio/PortfolioScreen";
import { track } from "@/lib/events";

/** Profilo-portfolio di un'altra persona (dal feed, da "Trova persone", dagli elenchi). */
export default function UserScreen() {
  const { nickname = "" } = useLocalSearchParams<{ nickname: string }>();
  const name = nickname.toLowerCase();
  const { profile } = useAuth();
  const self = profile?.nickname.toLowerCase() === name;
  useEffect(() => {
    if (name && !self) track({ name: "profile_view", nickname: name });
  }, [name, self]);
  return <PortfolioScreen nickname={name} />;
}
