import { fontSizes, spacing } from "@wearx/design-tokens";

/**
 * "WEARX" in Archivo Expanded 900 è largo circa 4,74 volte la dimensione del carattere: a 84 pt
 * (prototipo) misura ~398 pt e su un iPhone (393 pt meno i margini) andava a capo dopo "WEA"
 * (seduta 26). La dimensione si riduce quanto serve per stare su una riga.
 */
const LOGO_WIDTH_EM = 4.9;

export function logoSize(screenWidth: number, gutter: number = spacing[7]): number {
  const available = screenWidth - 2 * gutter;
  return Math.max(40, Math.min(fontSizes.logo, Math.floor(available / LOGO_WIDTH_EM)));
}
