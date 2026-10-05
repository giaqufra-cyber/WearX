/** Testi degli stili: numero di membri e fine della stagione, in italiano. */

const MONTHS = ["GEN", "FEB", "MAR", "APR", "MAG", "GIU", "LUG", "AGO", "SET", "OTT", "NOV", "DIC"];

function compact(value: number, unit: string): string {
  // Una cifra decimale con la virgola, senza ",0": 15,1k · 2k · 1,2M
  const rounded = Math.floor(value * 10) / 10;
  return `${rounded.toFixed(rounded % 1 === 0 ? 0 : 1).replace(".", ",")}${unit}`;
}

/** 1 membro · 950 membri · 15,1k membri · 1,2M membri */
export function membersLabel(count: number): string {
  if (count === 1) return "1 membro";
  if (count < 1000) return `${count} membri`;
  if (count < 1_000_000) return `${compact(count / 1000, "k")} membri`;
  return `${compact(count / 1_000_000, "M")} membri`;
}

/** "2026-11-01" -> "FINO AL 1 NOV" (l'ultimo giorno in cui lo stile è attivo). */
export function seasonEndLabel(isoDate: string): string {
  const [, month, day] = isoDate.split("-").map(Number);
  return `FINO AL ${day} ${MONTHS[(month ?? 1) - 1]}`;
}

/** "12 stili" / "1 stile" */
export function stylesCountLabel(count: number): string {
  return count === 1 ? "1 stile" : `${count} stili`;
}

/** 950 · 1,2k · 15,1k · 1,2M (statistiche del profilo). */
export function compactNumber(count: number): string {
  if (count < 1000) return String(count);
  if (count < 1_000_000) return compact(count / 1000, "k");
  return compact(count / 1_000_000, "M");
}
