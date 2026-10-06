import { Platform } from "react-native";

/**
 * Stato "attivo/non attivo" di un pulsante a interruttore (seduta 24, audit di accessibilità).
 * Sul web è aria-pressed (aria-selected su un pulsante non è valido); su iOS e Android
 * "selezionato", l'unico che VoiceOver e TalkBack leggono su un pulsante.
 */
export function toggleState(on: boolean): Record<string, boolean> {
  return Platform.OS === "web" ? { "aria-pressed": on } : { "aria-selected": on };
}
