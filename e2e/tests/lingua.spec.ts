import { expect, test } from "@playwright/test";

import { login, state } from "./helpers";

// Telefono in inglese: l'app parla inglese (seduta 33), anche nei testi del server (seduta 34).
test.use({ locale: "en-GB" });

test("lingua: con il telefono in inglese l'app è in inglese, e si può tornare all'italiano", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Create your account" })).toBeVisible();
  await expect(page.getByText("WearX is only for people aged 16 or over.")).toBeVisible();

  const { people } = await state();
  await login(page, people["anna.e2e"]!, { submit: "Sign in" });
  await expect(page.getByText("STYLES", { exact: true })).toBeVisible();

  // Nomi e descrizioni degli stili arrivano dal server, in inglese.
  await page.goto("/explore");
  await page.getByRole("searchbox").fill("gioielli");
  await expect(page.getByText("Jewellery", { exact: true })).toBeVisible();
  await expect(page.getByText("Chains, rings, gold and silver")).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Privacy and security" })).toBeVisible();
  await page.getByRole("radio", { name: "Italiano" }).click();
  await expect(page.getByRole("heading", { name: "Privacy e sicurezza" })).toBeVisible();
  // La scelta resta anche ricaricando.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Privacy e sicurezza" })).toBeVisible();
  await page.goto("/explore");
  await page.getByRole("searchbox").fill("jewellery");
  await expect(page.getByText("Gioielli", { exact: true })).toBeVisible();
});
