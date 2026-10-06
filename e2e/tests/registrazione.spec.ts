import { expect, test } from "@playwright/test";

import { offlineServices, unique } from "./helpers";

test("registrazione completa: account, codice, età, stili, primo feed", async ({ page }) => {
  await offlineServices(page);
  const nickname = unique("nuova.");
  await page.goto("/");
  await page.getByRole("button", { name: "Crea il tuo account" }).click();

  await page.getByRole("textbox", { name: "NICKNAME" }).fill(nickname);
  await page.getByRole("textbox", { name: "EMAIL" }).fill(`${nickname}@e2e.test`);
  await page.getByRole("textbox", { name: "PASSWORD" }).fill("Una-password-lunga-2026!");
  await page.getByRole("textbox", { name: "GIORNO" }).fill("14");
  await page.getByRole("textbox", { name: "MESE" }).fill("03");
  await page.getByRole("textbox", { name: "ANNO" }).fill("2003");
  await page.getByRole("checkbox", { name: /Informativa privacy/ }).click();
  await page.getByRole("checkbox", { name: /regole della community/ }).click();
  await page.getByRole("button", { name: "Continua" }).click();

  // Codice di conferma (l'Auth di prova accetta sempre 123456).
  await expect(page).toHaveURL(/\/verify/);
  // Con 6 cifre la conferma parte da sola.
  await page.getByRole("textbox", { name: "CODICE" }).fill("123456");
  await expect(page).not.toHaveURL(/\/verify/);

  // Verifica dell'età: si apre la pagina del fornitore (qui quello di prova dell'API).
  await expect(page.getByRole("heading", { name: /Confermiamo/ })).toBeVisible();
  const popupPromise = page.waitForEvent("popup");
  await page.getByRole("button", { name: /Stima con selfie/ }).click();
  const popup = await popupPromise;
  await popup.waitForLoadState();
  await expect(popup.getByRole("heading", { name: "Verifica dell'età" })).toBeVisible();
  await popup.getByRole("button", { name: "Ho 18 anni o più" }).click();
  await popup.waitForEvent("close", { timeout: 5_000 }).catch(() => undefined);

  // Tipo di profilo, poi gli stili.
  await expect(page.getByRole("heading", { name: "Che profilo vuoi?" })).toBeVisible();
  await page.getByRole("button", { name: "Continua" }).click();
  await expect(page.getByRole("heading", { name: "In che stile ti senti oggi?" })).toBeVisible();
  await page.getByRole("checkbox", { name: /^Old Money/ }).click();
  await page.getByRole("checkbox", { name: /^Elegant/ }).click();
  await expect(page.getByText("2 STILI")).toBeVisible();
  await page.getByRole("button", { name: "Entra in WearX" }).click();

  // Dentro: il feed con i fit degli stili scelti (ci sono quelli di giulia.e2e in Old Money).
  await expect(page).toHaveURL(/\/(feed)?$/);
  await expect(page.getByRole("alert")).toContainText(`Benvenuto su WearX, @${nickname}.`);
  await expect(page.getByRole("button", { name: "Old Money" })).toBeVisible();
  await expect(page.getByRole("article").first()).toBeVisible();
  await expect(page.getByRole("tab", { name: "Feed dei tuoi stili" })).toHaveAttribute("aria-selected", "true");
});
