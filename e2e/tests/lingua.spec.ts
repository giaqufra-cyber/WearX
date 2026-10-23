import { expect, test } from "@playwright/test";

import { login, state } from "./helpers";

// Telefono in inglese: l'app parla inglese (seduta 33).
test.use({ locale: "en-GB" });

test("lingua: con il telefono in inglese l'app è in inglese, e si può tornare all'italiano", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Create your account" })).toBeVisible();
  await expect(page.getByText("WearX is only for people aged 16 or over.")).toBeVisible();

  const { people } = await state();
  await login(page, people["anna.e2e"]!, { submit: "Sign in" });
  await expect(page.getByText("STYLES", { exact: true })).toBeVisible();

  await page.goto("/settings");
  await expect(page.getByRole("heading", { name: "Privacy and security" })).toBeVisible();
  await page.getByRole("radio", { name: "Italiano" }).click();
  await expect(page.getByRole("heading", { name: "Privacy e sicurezza" })).toBeVisible();
  // La scelta resta anche ricaricando.
  await page.reload();
  await expect(page.getByRole("heading", { name: "Privacy e sicurezza" })).toBeVisible();
});
