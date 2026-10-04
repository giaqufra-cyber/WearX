/**
 * Controlli immediati nei form, per dare un riscontro mentre si scrive.
 * Il server resta l'unica autorità: queste regole devono restare allineate a
 * services/api/app/text_policy.py, ma non lo sostituiscono.
 */

export const NICKNAME_RE = /^[a-z0-9._]{3,20}$/;
const RESERVED_FRAGMENTS = ["wearx", "admin", "moderat", "support", "staff", "official", "ufficial"];

export type NicknameHint = "empty" | "invalid" | "reserved" | "ok";

export function nicknameHint(raw: string): NicknameHint {
  const nickname = raw.trim().toLowerCase();
  if (nickname === "") return "empty";
  if (!NICKNAME_RE.test(nickname)) return "invalid";
  if (/^[._]|[._]$|\.\./.test(nickname)) return "invalid";
  const compact = nickname.replace(/[._]/g, "");
  if (RESERVED_FRAGMENTS.some((f) => compact.includes(f))) return "reserved";
  return "ok";
}

export type PasswordScore = 0 | 1 | 2 | 3 | 4;

/** Stesso punteggio del prototipo: lunghezza ≥ 10, numero, simbolo, maiuscole e minuscole. */
export function passwordScore(password: string): PasswordScore {
  let score = 0;
  if (password.length >= 10) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score += 1;
  return score as PasswordScore;
}

export const PASSWORD_MIN_SCORE: PasswordScore = 3;

export const PASSWORD_LABELS: Record<PasswordScore, string> = {
  0: "Troppo debole",
  1: "Debole",
  2: "Quasi",
  3: "Buona",
  4: "Ottima",
};

export const MIN_AGE = 16;

/**
 * Età compiuta a una certa data. Restituisce null se la data non esiste
 * (es. 31/02 o 29/02 in un anno non bisestile) o è nel futuro.
 */
export function ageOn(day: number, month: number, year: number, today: Date): number | null {
  if (![day, month, year].every(Number.isInteger)) return null;
  if (year < 1900 || month < 1 || month > 12 || day < 1) return null;
  const birth = new Date(Date.UTC(year, month - 1, day));
  if (birth.getUTCFullYear() !== year || birth.getUTCMonth() !== month - 1 || birth.getUTCDate() !== day) {
    return null;
  }
  const t = { y: today.getFullYear(), m: today.getMonth() + 1, d: today.getDate() };
  let age = t.y - year;
  if (t.m < month || (t.m === month && t.d < day)) age -= 1;
  return age < 0 ? null : age;
}

export const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
/** Numero in formato internazionale o italiano, solo cifre e spazi dopo l'eventuale +. */
export const PHONE_RE = /^\+?[0-9 ]{8,16}$/;
