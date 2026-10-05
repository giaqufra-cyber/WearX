import { describe, expect, test } from "vitest";

import { dueLabel, mainReason, queueCommand, slugify } from "@/lib/format";

describe("testi del pannello", () => {
  test("motivo prevalente: prima i minori, poi il più segnalato", () => {
    expect(mainReason({ spam: 3, nudity: 1 })).toBe("spam");
    expect(mainReason({ spam: 5, minor_safety: 1 })).toBe("minor_safety");
    expect(mainReason({ nudity: 2, harassment: 2 })).toBe("nudity");
    expect(mainReason({})).toBe("other");
  });

  test("scadenza", () => {
    const now = new Date("2026-10-05T10:00:00Z");
    expect(dueLabel("2026-10-05T10:40:00Z", now)).toBe("scade tra 40 min");
    expect(dueLabel("2026-10-05T15:00:00Z", now)).toBe("scade tra 5 h");
    expect(dueLabel("2026-10-08T10:00:00Z", now)).toBe("scade tra 3 g");
    expect(dueLabel("2026-10-05T08:00:00Z", now)).toBe("in ritardo di 2 h");
  });

  test("scorciatoie, ma non mentre si scrive", () => {
    expect(queueCommand({ key: "j" })).toBe("next");
    expect(queueCommand({ key: "a" })).toBe("dismiss");
    expect(queueCommand({ key: "r" })).toBe("remove");
    expect(queueCommand({ key: "a", metaKey: true })).toBeNull();
    expect(queueCommand({ key: "z" })).toBeNull();
    const textarea = document.createElement("textarea");
    expect(queueCommand({ key: "a", target: textarea })).toBeNull();
  });

  test("slug dal nome", () => {
    expect(slugify("Après Ski")).toBe("apres-ski");
    expect(slugify("  Old  Money!! ")).toBe("old-money");
    expect(slugify("Y2K")).toBe("y2k");
  });
});
