/** Validazione del modulo di registrazione (prototipo, schermata "Crea account"). */
import {
  ageOn,
  EMAIL_RE,
  MIN_AGE,
  nicknameHint,
  PASSWORD_MIN_SCORE,
  passwordScore,
  PHONE_RE,
} from "@/lib/validation";

export type SignupForm = {
  nickname: string;
  contactMode: "email" | "phone";
  contact: string;
  password: string;
  day: string;
  month: string;
  year: string;
  acceptTerms: boolean;
  acceptRules: boolean;
};

export type SignupErrors = Partial<Record<"nickname" | "contact" | "password" | "birth", string>>;

export type SignupCheck = {
  errors: SignupErrors;
  /** Età calcolata, null se la data non è completa o non esiste. */
  age: number | null;
  /** Sotto i 16 anni: la registrazione si ferma e non si salva nulla. */
  underage: boolean;
  canSubmit: boolean;
};

export const emptySignup: SignupForm = {
  nickname: "",
  contactMode: "email",
  contact: "",
  password: "",
  day: "",
  month: "",
  year: "",
  acceptTerms: false,
  acceptRules: false,
};

/**
 * Gli errori si mostrano solo per i campi già compilati: un campo vuoto non è "sbagliato",
 * è solo da completare (il pulsante resta disattivo).
 */
export function checkSignup(form: SignupForm, today: Date): SignupCheck {
  const errors: SignupErrors = {};

  const hint = nicknameHint(form.nickname);
  if (hint === "invalid") errors.nickname = "Solo minuscole, numeri, punto e underscore (da 3 a 20).";
  if (hint === "reserved") errors.nickname = "Questo nickname non è disponibile.";

  const contact = form.contact.trim();
  const contactOk = form.contactMode === "email" ? EMAIL_RE.test(contact) : PHONE_RE.test(contact);
  if (contact !== "" && !contactOk) {
    errors.contact = form.contactMode === "email" ? "Controlla l'indirizzo email." : "Controlla il numero.";
  }

  const score = passwordScore(form.password);
  if (form.password !== "" && score < PASSWORD_MIN_SCORE) {
    errors.password = "Serve una password più robusta.";
  }

  const filled = form.day !== "" && form.month !== "" && form.year.length === 4;
  const age = filled ? ageOn(Number(form.day), Number(form.month), Number(form.year), today) : null;
  if (filled && age === null) errors.birth = "Questa data non esiste.";
  const underage = age !== null && age < MIN_AGE;
  if (age !== null && age > 110) errors.birth = "Controlla l'anno di nascita.";

  const canSubmit =
    hint === "ok" &&
    contactOk &&
    score >= PASSWORD_MIN_SCORE &&
    age !== null &&
    !underage &&
    !errors.birth &&
    form.acceptTerms &&
    form.acceptRules;

  return { errors, age, underage, canSubmit };
}

/** Telefono in formato E.164 (+39…): Supabase lo richiede così. */
export function normalizePhone(raw: string): string {
  const digits = raw.replace(/[^\d+]/g, "");
  if (digits.startsWith("+")) return digits;
  if (digits.startsWith("00")) return `+${digits.slice(2)}`;
  return `+39${digits}`;
}
