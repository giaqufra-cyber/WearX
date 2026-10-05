import * as Sentry from "@sentry/react-native";

import { anonymizePath, initSentry, scrubBreadcrumb, scrubEvent } from "@/lib/sentry";

jest.mock("@sentry/react-native", () => ({ init: jest.fn() }));

test("indirizzi senza id, nickname né query", () => {
  expect(anonymizePath("https://api.wearx.app/v1/users/giulia.rossi/portfolio?cursor=abc")).toBe(
    "https://api.wearx.app/v1/users/…/portfolio",
  );
  expect(anonymizePath("/v1/posts/5d97583d-950d-417e-9a6c-494e15d15aa7/vote")).toBe("/v1/posts/…/vote");
  expect(anonymizePath("/user/fra.fit")).toBe("/user/…");
  expect(anonymizePath("/r/Z29fYWJjZGVm")).toBe("/r/…");
  expect(anonymizePath("/settings")).toBe("/settings");
  expect(anonymizePath("/v1/me/insights?days=7")).toBe("/v1/me/insights");
});

test("evento senza persona", () => {
  const event = scrubEvent({
    type: undefined,
    user: { id: "u1", email: "a@b.it", ip_address: "1.2.3.4" },
    server_name: "telefono",
    request: {
      url: "https://api.wearx.app/v1/users/giulia.rossi?q=1",
      headers: { Authorization: "Bearer x" },
      cookies: { a: "b" },
      data: { password: "x" },
      query_string: "q=1",
    },
  });
  expect(event.user).toBeUndefined();
  expect(event.server_name).toBeUndefined();
  expect(event.request).toEqual({ url: "https://api.wearx.app/v1/users/…" });
});

test("briciole: niente console e tocchi, indirizzi ripuliti", () => {
  expect(scrubBreadcrumb({ category: "console", message: "email a@b.it" })).toBeNull();
  expect(scrubBreadcrumb({ category: "touch", message: "Vota" })).toBeNull();
  expect(scrubBreadcrumb({ category: "ui.click" })).toBeNull();
  expect(
    scrubBreadcrumb({
      category: "fetch",
      data: { url: "https://api.wearx.app/v1/users/giulia.rossi", method: "GET", status_code: 200 },
    }),
  ).toEqual({ category: "fetch", data: { url: "https://api.wearx.app/v1/users/…", method: "GET", status_code: 200 } });
  expect(
    scrubBreadcrumb({ category: "navigation", data: { from: "/post/abc-123", to: "/user/fra.fit", params: { nickname: "fra.fit" } } }),
  ).toEqual({ category: "navigation", data: { from: "/post/…", to: "/user/…" } });
});

test("si accende solo con il DSN e senza dati personali", () => {
  expect(initSentry(undefined)).toBe(false);
  expect(Sentry.init).not.toHaveBeenCalled();
  expect(initSentry("https://abc@o1.ingest.de.sentry.io/2")).toBe(true);
  const options = (Sentry.init as jest.Mock).mock.calls[0][0];
  expect(options).toMatchObject({
    sendDefaultPii: false,
    attachScreenshot: false,
    attachViewHierarchy: false,
    tracesSampleRate: 0,
  });
});
