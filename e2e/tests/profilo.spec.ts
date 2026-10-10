import path from "node:path";

import { expect, test } from "@playwright/test";

import { login, state } from "./helpers";

test("modifica profilo: bio e foto profilo, i tuoi stili", async ({ page }) => {
  const { people } = await state();
  await login(page, people["marco.e2e"]!);
  await page.getByRole("tab", { name: "Il tuo profilo" }).click();
  await expect(page.getByLabel(/^I tuoi stili:/)).toBeVisible();
  await page.getByRole("button", { name: "Modifica profilo" }).click();
  await expect(page.getByRole("heading", { name: "Modifica profilo" })).toBeVisible();

  await page.getByRole("textbox", { name: "Bio" }).fill("Giacche in denim e treni regionali.");
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Scegli una foto" }).click();
  await (await chooser).setFiles(path.join(__dirname, "fit.jpg"));
  // Caricamento, controlli e varianti nel worker, come per le foto dei fit.
  await expect(page.getByText("Foto pronta: tocca Salva.")).toBeVisible({ timeout: 30_000 });
  const saved = page.waitForResponse((r) => r.url().endsWith("/v1/me") && r.request().method() === "PATCH");
  await page.getByRole("button", { name: "Salva" }).click();
  const body = (await (await saved).json()) as { bio: string; avatar: { urls: { variants: Record<string, string> } } | null };
  expect(body.bio).toBe("Giacche in denim e treni regionali.");
  expect(Object.keys(body.avatar?.urls.variants ?? {})).toContain("320");

  await expect(page.getByText("Profilo aggiornato.")).toBeVisible();
  await expect(page.getByText("Giacche in denim e treni regionali.")).toBeVisible();
});
