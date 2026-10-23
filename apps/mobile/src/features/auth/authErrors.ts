import { N_, t } from "@/lib/i18n";
/** Messaggi (italiano o inglese) per gli errori di Supabase Auth (si guarda il `code`, non il testo inglese). */

type MaybeAuthError = { code?: unknown; status?: unknown; message?: unknown } | null | undefined;

const MESSAGES: Record<string, string> = {
  invalid_credentials: N_("Email o password non corrette."),
  email_not_confirmed: N_("Prima conferma l'email con il codice che ti abbiamo mandato."),
  user_already_exists: N_("Esiste già un account con questo contatto. Prova ad accedere."),
  email_exists: N_("Esiste già un account con questa email. Prova ad accedere."),
  phone_exists: N_("Esiste già un account con questo numero. Prova ad accedere."),
  weak_password: N_("La password non è abbastanza robusta."),
  otp_expired: N_("Il codice è scaduto o non è corretto. Chiedine uno nuovo."),
  over_email_send_rate_limit: N_("Hai chiesto troppi codici. Aspetta un minuto e riprova."),
  over_sms_send_rate_limit: N_("Hai chiesto troppi codici. Aspetta un minuto e riprova."),
  over_request_rate_limit: N_("Troppi tentativi. Aspetta qualche minuto."),
  signup_disabled: N_("Le registrazioni sono momentaneamente chiuse."),
  sms_send_failed: N_("Non riusciamo a mandare l'SMS. Usa l'email."),
  email_address_invalid: N_("Questo indirizzo email non è accettato."),
};

export function authErrorMessage(error: MaybeAuthError): string {
  const code = typeof error?.code === "string" ? error.code : undefined;
  if (code && MESSAGES[code]) return t(MESSAGES[code]);
  if (error?.status === 429) return t(MESSAGES.over_request_rate_limit!);
  return t("Qualcosa non ha funzionato. Controlla la connessione e riprova.");
}
