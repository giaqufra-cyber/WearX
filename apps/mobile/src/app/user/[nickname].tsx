import { useLocalSearchParams } from "expo-router";

import { PortfolioScreen } from "@/features/portfolio/PortfolioScreen";

/** Profilo-portfolio di un'altra persona (dal feed, da "Trova persone", dagli elenchi). */
export default function UserScreen() {
  const { nickname = "" } = useLocalSearchParams<{ nickname: string }>();
  return <PortfolioScreen nickname={nickname.toLowerCase()} />;
}
