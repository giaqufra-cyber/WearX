import { expect, test } from "@playwright/test";

import { login, state } from "./helpers";

test("salvati: si salva un fit dal feed e si ritrova nel profilo", async ({ page }) => {
  const { people } = await state();
  await login(page, people["marco.e2e"]!);
  const first = page.getByRole("article").first();
  await expect(first).toBeVisible();
  await first.getByRole("button", { name: "Salva il fit" }).click();
  await expect(page.getByRole("alert")).toContainText("Salvato.");
  await expect(first.getByRole("button", { name: "Togli dai salvati" })).toBeVisible();

  await page.goto("/profile");
  await page.getByRole("button", { name: "Salvati" }).first().click();
  await expect(page.getByRole("heading", { name: "Salvati" })).toBeVisible();
  await expect(page.getByRole("button", { name: /^Fit,/ })).toHaveCount(1);
  await page.getByRole("button", { name: /^Fit,/ }).click();
  await expect(page.getByRole("button", { name: "Togli dai salvati" })).toBeVisible();
  await page.getByRole("button", { name: "Togli dai salvati" }).click();
  await page.goto("/saved");
  await expect(page.getByText("Ancora nessun fit salvato")).toBeVisible();
});
