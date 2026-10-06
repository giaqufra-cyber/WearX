import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

import { staffToken } from "./helpers";

/** Audit di accessibilità del pannello dello staff (seduta 24): WCAG 2.2 A/AA e buone pratiche. */
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];

async function violations(page: Page, screen: string) {
  await page.waitForLoadState("networkidle");
  const result = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  return result.violations.map((v) => ({
    screen,
    rule: v.id,
    impact: v.impact,
    help: v.help,
    targets: v.nodes.slice(0, 4).map((n) => `${n.target.join(" ")} | ${n.failureSummary?.split("\n")[1] ?? ""}`),
  }));
}

test("pannello: accesso", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Accedi" })).toBeVisible();
  expect(await violations(page, "accesso")).toEqual([]);
});

test("pannello: tutte le sezioni", async ({ page }) => {
  const token = await staffToken();
  await page.addInitScript((t) => window.sessionStorage.setItem("wearx-admin-dev-token", t), token);
  const found = [];
  for (const path of ["/", "/queue", "/appeals", "/users", "/users/giulia.e2e", "/votes", "/domains", "/styles", "/staff", "/audit"]) {
    await page.goto(path);
    await expect(page.getByRole("navigation").first()).toBeVisible();
    found.push(...(await violations(page, path)));
  }
  expect(found, JSON.stringify(found, null, 2)).toEqual([]);
});
