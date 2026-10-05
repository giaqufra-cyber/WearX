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
export type Post = Schemas["PostOut"];
export type FeedPage = Schemas["FeedOut"];
export type VoteSummary = Schemas["VoteSummary"];
export type VoteRequest = Schemas["VoteIn"];
export type PostCreate = Schemas["PostIn"];
export type PostUpdate = Schemas["PostPatch"];
export type PostItem = Schemas["ItemOut"];
export type PostItemInput = Schemas["ItemIn"];
export type MediaUpload = Schemas["UploadOut"];
export type MediaUploadRequest = Schemas["UploadIn"];
export type StyleCard = Schemas["StyleCard"];
export type StyleDetail = Schemas["StyleDetail"];
export type StyleList = Schemas["StyleList"];
export type AgeStatus = Schemas["AgeStatusOut"];
export type AgeSession = Schemas["AgeSessionOut"];
export type AgeSessionRequest = Schemas["AgeSessionIn"];
export type AgeMethod = Schemas["AgeSessionIn"]["method"];
export type UserProfile = Schemas["UserOut"];
export type PortfolioPage = Schemas["PortfolioPage"];
export type PortfolioTile = Schemas["PortfolioTile"];
export type PortfolioOrder = Schemas["OrderIn"];
export type Capsule = Schemas["CapsuleOut"];
export type CapsuleInput = Schemas["CapsuleIn"];
export type Relationship = Schemas["Relationship"];
export type FollowState = Schemas["FollowOut"]["following"];
export type PersonSummary = Schemas["PersonOut"];
export type PeoplePage = Schemas["PeoplePage"];
export type FollowRequestDecision = Schemas["RequestDecision"];
export type ReportRequest = Schemas["ReportIn"];
export type ReportReason = Schemas["ReportIn"]["reason"];
export type ReportReceipt = Schemas["ReportOut"];
export type ModerationNotice = Schemas["NoticeOut"];
export type Appeal = Schemas["AppealOut"];
export type AppNotification = Schemas["NotificationOut"];
export type NotificationPage = Schemas["NotificationPage"];
export type NotificationType = Schemas["NotificationOut"]["type"];
export type NotificationSettings = Schemas["NotificationSettings"];
export type NotificationSettingsUpdate = Schemas["NotificationSettingsPatch"];
export type PushTokenRequest = Schemas["PushTokenIn"];
export type UsageEvent = Schemas["EventBatch"]["events"][number];
export type UsageEventBatch = Schemas["EventBatch"];
export type Insights = Schemas["InsightsOut"];
export type InsightMetric = Schemas["Metric"];
export type InsightPoint = Schemas["InsightPoint"];
export type InsightPost = Schemas["InsightPost"];
export type InsightPeriod = Schemas["InsightsOut"]["days"];
export type Device = Schemas["DeviceOut"];
export type DeviceInfo = Schemas["DeviceIn"];
export type DataExport = Schemas["ExportOut"];
export type DeletionRequest = Schemas["DeletionIn"];
export type DeletionScheduled = Schemas["DeletionOut"];
export type DeletionStatus = Schemas["DeletionStatus"];
export type ShopLink = Schemas["LinkOut"];
export type ShopDomain = Schemas["ShopDomainOut"];
export type BlockedDomain = Schemas["BlockedDomainOut"];
export type BlockedDomainCreate = Schemas["BlockedDomainIn"];

// Pannello dello staff (/v1/admin)
export type StaffMe = Schemas["StaffMe"];
export type AdminStats = Schemas["Stats"];
export type QueueItem = Schemas["QueueItem"];
export type ModerationDecision = Schemas["DecisionIn"];
export type ModerationDecisionResult = Schemas["DecisionOut"];
export type AdminPost = Schemas["AdminPost"];
export type AdminUserRow = Schemas["UserRow"];
export type UserCase = Schemas["UserCase"];
export type ModerationAction = Schemas["ActionOut"];
export type SanctionRequest = Schemas["SanctionIn"];
export type AppealItem = Schemas["AppealItem"];
export type AppealDecision = Schemas["AppealDecisionIn"];
export type AdminStyle = Schemas["AdminStyle"];
export type AdminStyleCreate = Schemas["StyleCreate"];
export type AdminStyleUpdate = Schemas["StyleFields"];
export type StaffRow = Schemas["StaffRow"];
export type AuditPage = Schemas["AuditPage"];
export type AuditRow = Schemas["AuditRow"];

/** Codici di errore stabili restituiti dall'API (campo `code` di problem+json). */
export type ApiErrorCode =
  | "account.business_requires_adult"
  | "account.pending_deletion"
  | "account.posting_restricted"
  | "account.suspended"
  | "age.already_verified"
  | "age.bad_return_url"
  | "age.blocked"
  | "age.invalid_birth_date"
  | "age.method_unavailable"
  | "age.provider_unavailable"
  | "age.session_not_found"
  | "age.underage"
  | "age.verification_required"
  | "app.update_required"
  | "appeal.decided"
  | "appeal.exists"
  | "appeal.expired"
  | "appeal.not_allowed"
  | "appeal.not_found"
  | "appeal.same_moderator"
  | "appeal.text_required"
  | "auth.anonymous_not_allowed"
  | "auth.invalid_token"
  | "auth.required"
  | "auth.session_revoked"
  | "auth.token_expired"
  | "auth.unavailable"
  | "block.self"
  | "business.required"
  | "capsule.limit"
  | "capsule.name_required"
  | "capsule.name_taken"
  | "capsule.not_found"
  | "deletion.already"
  | "deletion.confirm_mismatch"
  | "deletion.none"
  | "deletion.suspended"
  | "device.current"
  | "device.not_found"
  | "export.too_soon"
  | "feature.disabled"
  | "feed.cursor_expired"
  | "feed.invalid_cursor"
  | "follow.not_allowed"
  | "follow.request_not_found"
  | "follow.self"
  | "insights.bad_period"
  | "insights.disabled"
  | "item.bad_media_position"
  | "item.incomplete"
  | "link.invalid"
  | "link.not_found"
  | "media.duplicate"
  | "media.not_found"
  | "media.not_uploaded"
  | "media.too_large"
  | "media.too_many_pending"
  | "media.unavailable"
  | "moderation.bad_decision"
  | "moderation.bad_ground"
  | "moderation.not_found"
  | "nickname.invalid"
  | "nickname.reserved"
  | "nickname.taken"
  | "notifications.invalid_cursor"
  | "onboarding.required"
  | "people.invalid_cursor"
  | "portfolio.bad_position"
  | "portfolio.invalid_cursor"
  | "post.not_found"
  | "post.not_owner"
  | "post.restyle_used"
  | "profile.exists"
  | "profile.private"
  | "push.bad_token"
  | "rate.limited"
  | "report.own_content"
  | "request.in_progress"
  | "request.invalid"
  | "resource.not_found"
  | "server.error"
  | "shop.limit"
  | "shop.not_found"
  | "shop.taken"
  | "shop.verify_failed"
  | "staff.admin_required"
  | "staff.last_admin"
  | "staff.mfa_required"
  | "style.age_restricted"
  | "style.bad_dates"
  | "style.last_membership"
  | "style.limit"
  | "style.not_found"
  | "style.slug_taken"
  | "terms.outdated"
  | "text.invalid_characters"
  | "text.not_allowed"
  | "text.too_long"
  | "text.too_many_lines"
  | "user.not_found"
  | "user.not_restricted"
  | "vote.not_allowed"
  | "vote.own_post"
  | "webhook.rejected"
  | "webhook.unknown_provider";
