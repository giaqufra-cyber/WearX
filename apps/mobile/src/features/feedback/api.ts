/** "Segnala un problema" (seduta 25): il messaggio arriva allo staff con versione, sistema e schermata. */
import { useMutation } from "@tanstack/react-query";
import type { Schemas } from "@wearx/api-types";
import { Platform } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { APP_VERSION, apiRequest } from "@/lib/api";

export type FeedbackKind = Schemas["FeedbackIn"]["kind"];

/** Solo le parti fisse del percorso ("/post/[id]"), mai id o nickname. */
export function screenFromSegments(segments: readonly string[]): string | null {
  const parts = segments.filter((s) => !(s.startsWith("(") && s.endsWith(")")));
  const path = `/${parts.join("/")}`;
  return /^\/[A-Za-z0-9_\-/[\]]*$/.test(path) && path.length <= 100 ? path : null;
}

export function deviceInfo(): Pick<Schemas["FeedbackIn"], "app_version" | "platform" | "os_version"> {
  const platform = Platform.OS === "ios" || Platform.OS === "android" ? Platform.OS : "web";
  const os = Platform.OS === "web" ? null : String(Platform.Version).slice(0, 20);
  return { app_version: APP_VERSION, platform, os_version: os };
}

export function useSendFeedback() {
  const { session } = useAuth();
  return useMutation({
    mutationFn: (input: { kind: FeedbackKind; message: string; screen: string | null }) =>
      apiRequest<Schemas["FeedbackCreated"]>("POST", "/v1/feedback", {
        token: session?.access_token,
        body: { ...input, ...deviceInfo() },
      }),
  });
}
