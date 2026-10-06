import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";

import { login, offlineServices, state } from "./helpers";

/**
 * Audit di accessibilità (seduta 24): axe-core, regole WCAG 2.2 livello A e AA, su ogni schermata
 * dell'app web, più le buone pratiche di axe. Il test fallisce se trova problemi; il dettaglio
 * va in test-results/axe-*.json.
 */
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"];

type Finding = { screen: string; rule: string; impact: string; help: string; targets: string[] };
const findings: Finding[] = [];

async function audit(page: Page, screen: string): Promise<void> {
  await page.waitForLoadState("networkidle");
  await page.waitForTimeout(400); // animazioni di entrata
  const result = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  for (const v of result.violations) {
    findings.push({
      screen,
      rule: v.id,
      impact: v.impact ?? "",
      help: v.help,
      targets: v.nodes.slice(0, 5).map((n) => `${n.target.join(" ")} | ${n.failureSummary?.split("\n")[1] ?? ""}`),
    });
  }
}

// Ogni test parte da zero: un test fallito non trascina i problemi nei successivi.
test.beforeEach(() => {
  findings.length = 0;
});

test.afterEach(() => {
  mkdirSync("test-results", { recursive: true });
  if (findings.length) writeFileSync(`test-results/axe-${Date.now()}.json`, JSON.stringify(findings, null, 2));
});

test("accessibilità: schermate senza accesso", async ({ page }) => {
  await offlineServices(page);
  for (const path of ["/welcome", "/login", "/signup", "/forgot"]) {
    await page.goto(path);
    await audit(page, path);
  }
  expect(findings, JSON.stringify(findings, null, 2)).toEqual([]);
});

test("accessibilità: schermate dell'app", async ({ page }) => {
  const { people, posts } = await state();
  await login(page, people["giulia.e2e"]!);
  const screens = [
    "/",
    "/explore",
    "/profile",
    "/create",
    "/new-post",
    "/notifications",
    "/settings",
    "/notification-settings",
    "/devices",
    "/people",
    "/find",
    "/style/old-money",
    `/post/${posts[0]}`,
    "/user/marco.e2e",
    "/moderation",
    "/data-export",
    "/change-password",
    "/account-type",
    "/insights",
  ];
  for (const path of screens) {
    await page.goto(path);
    await audit(page, `@giulia ${path}`);
  }
  expect(findings, JSON.stringify(findings, null, 2)).toEqual([]);
});

test("accessibilità: profilo privato visto da fuori e foglio di segnalazione", async ({ page }) => {
  const { people } = await state();
  await login(page, people["marco.e2e"]!);
  await page.goto("/user/giulia.e2e");
  await audit(page, "@marco /user/giulia.e2e");
  await page.goto("/");
  const card = page.getByRole("article").first();
  await expect(card).toBeVisible();
  await audit(page, "@marco feed");
  await card.getByRole("button", { name: "Segnala il fit" }).click();
  await expect(page.getByText("Spam")).toBeVisible();
  await audit(page, "@marco foglio azioni");
  expect(findings, JSON.stringify(findings, null, 2)).toEqual([]);
});
