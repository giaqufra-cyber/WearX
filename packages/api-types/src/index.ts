/**
 * Tipi dell'API WearX, generati da openapi.json (non modificare schema.ts a mano).
 * Rigenerare dopo ogni modifica all'API:  pnpm --filter @wearx/api-types sync
 * La CI fallisce se i tipi non corrispondono all'API.
 */
import type { components, paths } from "./schema";

export type { components, paths };
export type Schemas = components["schemas"];

export type AppConfig = Schemas["ConfigOut"];
export type Style = Schemas["StyleOut"];
export type Profile = Schemas["ProfileOut"];
export type ProfileUpdate = Schemas["ProfileUpdateIn"];
export type OnboardingRequest = Schemas["OnboardingIn"];
export type NicknameCheck = Schemas["NicknameCheckOut"];

/** Codici di errore stabili restituiti dall'API (campo `code` di problem+json). */
export type ApiErrorCode =
  | "app.update_required"
  | "auth.required"
  | "auth.invalid_token"
  | "auth.token_expired"
  | "auth.anonymous_not_allowed"
  | "auth.unavailable"
  | "account.suspended"
  | "account.business_requires_adult"
  | "age.verification_required"
  | "feature.disabled"
  | "nickname.invalid"
  | "nickname.reserved"
  | "nickname.taken"
  | "onboarding.required"
  | "profile.exists"
  | "rate.limited"
  | "request.invalid"
  | "resource.not_found"
  | "server.error"
  | "style.age_restricted"
  | "style.not_found"
  | "terms.outdated"
  | "text.invalid_characters"
  | "text.too_long"
  | "text.too_many_lines";
