import { expect, test } from "@playwright/test";

import { login, publishVotes, state } from "./helpers";

test("voto: si vota un fit, numero e media arrivano con l'aggiornamento orario", async ({ page }) => {
  const { people, posts } = await state();
  await login(page, people["marco.e2e"]!);
  // Il primo fit del feed (il feed carica i fit man mano che si scorre).
  const first = page.getByRole("article").first();
  await expect(first).toBeVisible();
  const captions = ["Capodanno a Trento", "Vernissage in Brera", "Domenica al mercato"];
  const text = (await first.textContent()) ?? "";
  const caption = captions.find((c) => text.includes(c))!;
  const card = page.getByRole("article").filter({ hasText: caption });
  await expect(card.getByText("VOTA IL FIT · 1–100")).toBeVisible();
  await card.getByRole("button", { name: "Un punto in più" }).click();
  await card.getByRole("button", { name: "Un punto in più" }).click();
  await expect(card.getByRole("slider", { name: "Il tuo voto da 1 a 100" })).toHaveAttribute("aria-valuenow", "72");
  await card.getByRole("radio", { name: "Sì" }).click();
  await card.getByRole("button", { name: "Vota" }).click();

  // Subito: il voto è registrato, media e numero non ancora (si aggiornano ogni ora).
  await expect(card.getByText("MEDIA COMMUNITY")).toBeVisible();
  await expect(card.getByText(/Voti in arrivo · il tuo 72/)).toBeVisible();
  await expect(card.getByText("La media compare da 5 voti · si aggiornano ogni ora")).toBeVisible();

  // Dopo il lavoro orario: 1 voto, la media ancora no (servono 5 voti).
  await publishVotes();
  await page.reload();
  // Si riapre lo stesso fit dalla sua pagina.
  await page.goto(`/post/${posts[captions.indexOf(caption)]}`);
  const again = page;
  await expect(again.getByText(caption)).toBeVisible();
  await expect(again.getByText(/1 voto · il tuo 72/)).toBeVisible();
  await expect(again.getByText(/^La media compare da 5 voti · aggiornati alle \d\d:\d\d$/)).toBeVisible();
});
