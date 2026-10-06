import path from "node:path";

import { expect, test } from "@playwright/test";

import { login, state } from "./helpers";

test("pubblicare un fit: foto, stile, capo, didascalia, elaborazione, nel portfolio", async ({ page }) => {
  const { people } = await state();
  await login(page, people["marco.e2e"]!);
  await page.getByRole("tab", { name: "Pubblica un fit" }).click();
  await expect(page.getByRole("heading", { name: "Nuovo fit" })).toBeVisible();

  // La "galleria" sul web è il selettore dei file del browser.
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Scegli le foto dalla galleria" }).click();
  await (await chooser).setFiles(path.join(__dirname, "fit.jpg"));
  await expect(page.getByText("1 di 10")).toBeVisible();

  await page.getByRole("radio", { name: "Streetwear" }).click();
  await page.getByRole("textbox", { name: "Brand del capo 1" }).fill("Officina");
  await page.getByRole("textbox", { name: "Nome del capo 1" }).fill("Giacca in denim");
  await page.getByRole("textbox", { name: "Prezzo in euro del capo 1" }).fill("89");
  await page.getByRole("textbox", { name: "Didascalia" }).fill("Prova end-to-end in centro");
  await page.getByRole("button", { name: "Pubblica" }).click();
  // Caricamento nell'archivio, elaborazione nel worker (EXIF via, varianti), pubblicazione.
  await expect(page.getByText("Fit pubblicato in Streetwear.")).toBeVisible({ timeout: 30_000 });

  await page.getByRole("tab", { name: "Il tuo profilo" }).click();
  const tile = page.getByRole("button", { name: "Fit 1, copertina, Streetwear, Prova end-to-end in centro" });
  await expect(tile).toBeVisible();
  await tile.click();
  await expect(page.getByText("Giacca in denim")).toBeVisible();
  await expect(page.getByText("Officina")).toBeVisible();
  await expect(page.getByText(/^89\s€$/).filter({ visible: true }).first()).toBeVisible();
});
