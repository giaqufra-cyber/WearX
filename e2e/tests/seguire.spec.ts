import { expect, test } from "@playwright/test";

import { login, state } from "./helpers";

test("account privato: richiesta di follow, accettazione, portfolio visibile", async ({ page, browser }) => {
  const { people } = await state();
  await login(page, people["marco.e2e"]!);
  await page.goto(`/user/${people["giulia.e2e"]!.nickname}`);
  await expect(page.getByRole("heading", { name: "Account privato" })).toBeVisible();
  await page.getByRole("button", { name: "Segui" }).click();
  await expect(page.getByRole("button", { name: "Richiesta inviata" })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("Richiesta inviata a @giulia.e2e.");

  const context = await browser.newContext();
  const giulia = await context.newPage();
  await login(giulia, people["giulia.e2e"]!);
  await giulia.getByRole("button", { name: "Notifiche" }).click();
  await expect(giulia.getByRole("button", { name: /@marco\.e2e vuole seguirti/ })).toBeVisible();
  await giulia.getByRole("button", { name: "Accetta", exact: true }).click();
  await expect(giulia.getByRole("button", { name: "Accetta", exact: true })).toHaveCount(0);
  await context.close();

  // Ora marco vede il portfolio di giulia (un fit è stato nascosto dalla moderazione in un altro
  // percorso: se ne vedono almeno due).
  await page.reload();
  await expect(page.getByRole("heading", { name: "Account privato" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Fit \d/ }).first()).toBeVisible();
  expect(await page.getByRole("button", { name: /^Fit \d/ }).count()).toBeGreaterThanOrEqual(2);
  await expect(page.getByRole("button", { name: "Segui già" })).toBeVisible();
});
