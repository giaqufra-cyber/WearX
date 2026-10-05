/** Testi del portfolio. */
import type { PortfolioTile, UserProfile } from "@wearx/api-types";

import { compactNumber } from "@/features/styles/format";

/** Posizione nella griglia: 1 -> "01". */
export function positionLabel(index: number): string {
  return String(index + 1).padStart(2, "0");
}

export function accountTypeLabel(type: UserProfile["account_type"]): string {
  return type === "business" ? "BUSINESS" : "PRIVATO";
}

/** Numero grande del tile e riga sotto: media e voti, o il motivo per cui non si vedono. */
export function tileScore(tile: PortfolioTile, own: boolean): { score: string; sub: string } {
  if (tile.average !== null) {
    const votes = tile.vote_count === null ? "media" : tile.vote_count === 1 ? "1 voto" : `${compactNumber(tile.vote_count)} voti`;
    return { score: String(Math.round(tile.average)), sub: votes };
  }
  if (own) return { score: "—", sub: "ancora nessun voto" };
  return { score: "?", sub: "vota per vedere" };
}

/** Stato del fit che solo l'autore vede sul tile. */
export function tileStatus(tile: PortfolioTile): string | null {
  if (tile.status === "style_rejected") return "FUORI STILE";
  if (tile.status === "hidden_moderation") return "NASCOSTO";
  return null;
}

export function statValue(value: number | null, kind: "count" | "average"): string {
  if (value === null) return "—";
  return kind === "average" ? String(Math.round(value)) : compactNumber(value);
}
