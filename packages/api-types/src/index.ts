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
export type MediaUpload = Schemas["UploadOut"];
export type MediaUploadRequest = Schemas["UploadIn"];
export type StyleCard = Schemas["StyleCard"];
export type StyleDetail = Schemas["StyleDetail"];
export type StyleList = Schemas["StyleList"];
export type AgeStatus = Schemas["AgeStatusOut"];
export type AgeSession = Schemas["AgeSessionOut"];
export type AgeSessionRequest = Schemas["AgeSessionIn"];
export type AgeMethod = Schemas["AgeSessionIn"]["method"];

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
  | "age.already_verified"
  | "age.bad_return_url"
  | "age.blocked"
  | "age.invalid_birth_date"
  | "age.method_unavailable"
  | "age.provider_unavailable"
  | "age.session_not_found"
  | "age.underage"
  | "age.verification_required"
  | "feature.disabled"
  | "media.not_found"
  | "media.not_uploaded"
  | "media.too_large"
  | "media.too_many_pending"
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
  | "style.last_membership"
  | "style.limit"
  | "style.not_found"
  | "terms.outdated"
  | "text.invalid_characters"
  | "text.too_long"
  | "text.too_many_lines"
  | "webhook.rejected"
  | "webhook.unknown_provider";
