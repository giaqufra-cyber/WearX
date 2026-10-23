/** Testi del portfolio. */
import type { PortfolioTile, UserProfile } from "@wearx/api-types";

import { compactNumber } from "@/features/styles/format";
import { t } from "@/lib/i18n";

/** Posizione nella griglia: 1 -> "01". */
export function positionLabel(index: number): string {
  return String(index + 1).padStart(2, "0");
}

export function accountTypeLabel(type: UserProfile["account_type"]): string {
  return type === "business" ? t("BUSINESS") : t("PRIVATO");
}

/** Numero grande del tile e riga sotto: media e voti, o il motivo per cui non si vedono. */
export function tileScore(tile: PortfolioTile, own: boolean): { score: string; sub: string } {
  if (tile.average !== null) {
    const votes =
      tile.vote_count === null
        ? t("media")
        : tile.vote_count === 1
          ? t("1 voto")
          : t("{count} voti", { count: compactNumber(tile.vote_count) });
    return { score: String(Math.round(tile.average)), sub: votes };
  }
  if (own) return { score: "—", sub: t("ancora nessun voto") };
  return { score: "?", sub: t("vota per vedere") };
}

/** Stato del fit che solo l'autore vede sul tile. */
export function tileStatus(tile: PortfolioTile): string | null {
  if (tile.status === "style_rejected") return t("FUORI STILE");
  if (tile.status === "hidden_moderation") return t("NASCOSTO");
  return null;
}

export function statValue(value: number | null, kind: "count" | "average"): string {
  if (value === null) return "—";
  return kind === "average" ? String(Math.round(value)) : compactNumber(value);
}
