import { N_, language, t, tn } from "@/lib/i18n";
/** Testi degli stili: numero di membri e fine della stagione. */

const MONTHS = [N_("GEN"), N_("FEB"), N_("MAR"), N_("APR"), N_("MAG"), N_("GIU"), N_("LUG"), N_("AGO"), N_("SET"), N_("OTT"), N_("NOV"), N_("DIC")];

function compact(value: number, unit: string): string {
  // Una cifra decimale con la virgola, senza ",0": 15,1k · 2k · 1,2M
  const rounded = Math.floor(value * 10) / 10;
  const text = rounded.toFixed(rounded % 1 === 0 ? 0 : 1);
  return `${language() === "en" ? text : text.replace(".", ",")}${unit}`;
}

/** 1 membro · 950 membri · 15,1k membri · 1,2M membri */
export function membersLabel(count: number): string {
  if (count < 1000) return tn(count, "{count} membro", "{count} membri");
  return t("{count} membri", { count: compactNumber(count) });
}

/** "2026-11-01" -> "FINO AL 1 NOV" (l'ultimo giorno in cui lo stile è attivo). */
export function seasonEndLabel(isoDate: string): string {
  const [, month, day] = isoDate.split("-").map(Number);
  return t("FINO AL {day} {month}", { day: day ?? 1, month: t(MONTHS[(month ?? 1) - 1] ?? "GEN") });
}

/** "12 stili" / "1 stile" */
export function stylesCountLabel(count: number): string {
  return tn(count, "{count} stile", "{count} stili");
}

/** 950 · 1,2k · 15,1k · 1,2M (statistiche del profilo). */
export function compactNumber(count: number): string {
  if (count < 1000) return String(count);
  if (count < 1_000_000) return compact(count / 1000, "k");
  return compact(count / 1_000_000, "M");
}
