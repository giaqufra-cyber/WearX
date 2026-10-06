import { expect, test } from "@playwright/test";

import { login, state, staffToken, API } from "./helpers";

test("segnala un problema: dall'app al pannello dello staff", async ({ page }) => {
  const { people } = await state();
  await login(page, people["marco.e2e"]!);
  await page.goto("/settings");
  await page.getByRole("button", { name: /^Segnala un problema/ }).click();
  await page.getByRole("radio", { name: "Non funziona" }).click();
  await page.getByLabel("Il tuo messaggio").fill("Il pulsante Vota a volte non risponde al primo tocco.");
  await page.getByRole("button", { name: "Invia al team" }).click();
  await expect(page.getByRole("alert").or(page.getByRole("status"))).toContainText("Il messaggio è arrivato al team");

  const token = await staffToken();
  const res = await fetch(`${API}/v1/admin/feedback`, { headers: { Authorization: `Bearer ${token}` } });
  const body = (await res.json()) as { items: { author: string; message: string; screen: string | null }[] };
  const mine = body.items.find((i) => i.author === "marco.e2e");
  expect(mine?.message).toBe("Il pulsante Vota a volte non risponde al primo tocco.");
  expect(mine?.screen).toBe("/settings");
});
