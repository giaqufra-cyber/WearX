/**
 * Crash e errori dell'app su Sentry (seduta 23), solo se c'è il DSN (EXPO_PUBLIC_SENTRY_DSN:
 * il DSN è pubblico per natura, serve solo a inviare). Nessun dato personale:
 * niente utente, niente IP, niente schermate o albero della vista, niente testi dei tocchi;
 * negli indirizzi restano solo le parti fisse (gli id, i nickname e le query diventano "…").
 */
import * as Sentry from "@sentry/react-native";
import Constants from "expo-constants";

type Event = Sentry.ErrorEvent;
type Breadcrumb = Sentry.Breadcrumb;

/** "/v1/users/giulia.rossi/portfolio?x=1" → "/v1/users/…/portfolio": restano solo le parti fisse. */
export function anonymizePath(url: string): string {
  let path = url;
  let origin = "";
  const match = /^(https?:\/\/[^/]+)(.*)$/.exec(url);
  if (match) {
    origin = match[1]!;
    path = match[2] || "/";
  }
  path = path.split(/[?#]/)[0]!;
  const parts = path.split("/").map((part, i) => {
    if (part === "" || (i === 1 && part === "v1")) return part;
    return /^[a-z-]+$/.test(part) && part.length <= 24 && !part.includes(".") ? part : "…";
  });
  // Dopo "users", "user", "style", "post", "r" viene sempre un identificativo.
  for (let i = 0; i < parts.length - 1; i++) {
    if (["users", "user", "post", "posts", "style", "styles", "r"].includes(parts[i]!)) parts[i + 1] = "…";
  }
  return origin + parts.join("/");
}

export function scrubEvent(event: Event): Event {
  delete event.user;
  delete event.server_name;
  if (event.request) {
    delete event.request.cookies;
    delete event.request.headers;
    delete event.request.data;
    delete event.request.query_string;
    if (event.request.url) event.request.url = anonymizePath(event.request.url);
  }
  return event;
}

export function scrubBreadcrumb(crumb: Breadcrumb): Breadcrumb | null {
  // I messaggi della console e i tocchi possono contenere testi scritti dalla persona.
  if (crumb.category === "console" || crumb.category === "touch" || crumb.category?.startsWith("ui.")) return null;
  const data = crumb.data ? { ...crumb.data } : undefined;
  if (data) {
    for (const key of ["url", "to", "from"]) {
      if (typeof data[key] === "string") data[key] = anonymizePath(data[key] as string);
    }
    delete data.params;
  }
  return { ...crumb, data };
}

let started = false;

export function initSentry(dsn: string | undefined = process.env.EXPO_PUBLIC_SENTRY_DSN): boolean {
  if (!dsn || started) return started;
  Sentry.init({
    dsn,
    environment: process.env.EXPO_PUBLIC_APP_ENV ?? (__DEV__ ? "development" : "production"),
    release: `wearx@${Constants.expoConfig?.version ?? "0.0.0"}`,
    sendDefaultPii: false,
    attachScreenshot: false,
    attachViewHierarchy: false,
    enableUserInteractionTracing: false,
    tracesSampleRate: 0,
    beforeSend: (event) => scrubEvent(event),
    beforeBreadcrumb: (crumb) => scrubBreadcrumb(crumb),
  });
  started = true;
  return true;
}
