/**
 * "Aggiorna l'app": quando l'API risponde 426 (app.update_required) o la configurazione dice
 * che la versione minima è più alta di questa, l'app mostra solo la schermata di aggiornamento.
 */
import { create } from "zustand";

type UpdateGate = { required: boolean };

export const useUpdateGate = create<UpdateGate>(() => ({ required: false }));

export function markUpdateRequired(): void {
  if (!useUpdateGate.getState().required) useUpdateGate.setState({ required: true });
}

/** "0.9.2" < "0.10.0": confronto numerico parte per parte (le parti mancanti valgono 0). */
export function isOlder(version: string, minimum: string): boolean {
  const parse = (v: string) => v.split(/[.+-]/).slice(0, 3).map((p) => Number.parseInt(p, 10) || 0);
  const [a, b] = [parse(version), parse(minimum)];
  for (let i = 0; i < 3; i++) {
    const diff = (a[i] ?? 0) - (b[i] ?? 0);
    if (diff !== 0) return diff < 0;
  }
  return false;
}
