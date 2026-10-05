import { useAuth } from "@/features/auth/AuthProvider";
import { PortfolioScreen } from "@/features/portfolio/PortfolioScreen";
import { Loading } from "@/ui/LoadState";

/** Il tuo profilo-portfolio (prototipo, schermata Profilo). */
export default function ProfileScreen() {
  const { profile } = useAuth();
  if (!profile) return <Loading label="Carico il profilo" />;
  return <PortfolioScreen nickname={profile.nickname} />;
}
