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
  // Il capo si segna sulla foto: tocco nel punto, poi "Fatto".
  await page.getByRole("button", { name: "Segna il capo 1 sulla foto" }).click();
  const photo = page.getByTestId("pin-photo");
  const box = (await photo.boundingBox())!;
  await photo.click({ position: { x: box.width * 0.3, y: box.height * 0.6 } });
  await page.getByRole("button", { name: "Fatto" }).click();
  await expect(page.getByText("Sulla foto 1 · Cambia")).toBeVisible();
  await page.getByRole("textbox", { name: "Didascalia" }).fill("Prova end-to-end in centro");
  const sent = page.waitForRequest((r) => r.url().endsWith("/v1/posts") && r.method() === "POST");
  await page.getByRole("button", { name: "Pubblica" }).click();
  const item = ((await sent).postDataJSON() as { items: Record<string, number>[] }).items[0]!;
  expect(item.media_position).toBe(0);
  expect(item.pin_x).toBeCloseTo(0.3, 1);
  expect(item.pin_y).toBeCloseTo(0.6, 1);
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
