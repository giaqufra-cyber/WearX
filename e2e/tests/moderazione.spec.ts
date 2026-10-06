import { expect, test } from "@playwright/test";

import { API, login, state, staffToken } from "./helpers";

const CAPTIONS = ["Capodanno a Trento", "Vernissage in Brera", "Domenica al mercato"];

test("segnalazione → decisione dello staff → avviso a chi ha pubblicato", async ({ page, browser }) => {
  const { people, posts } = await state();
  await login(page, people["marco.e2e"]!);
  const card = page.getByRole("article").first();
  const text = (await card.textContent()) ?? "";
  const caption = CAPTIONS.find((c) => text.includes(c))!;
  const postId = posts[CAPTIONS.indexOf(caption)]!;

  await card.getByRole("button", { name: "Segnala il fit" }).click();
  const sheet = page.getByRole("dialog", { name: "Segnala il fit" });
  await sheet.getByRole("radio", { name: "Spam" }).click();
  await sheet.getByRole("button", { name: "Invia segnalazione" }).click();
  await expect(page.getByRole("dialog", { name: "Grazie" })).toContainText("Non diciamo a nessuno chi l'ha fatta.");

  // Lo staff decide (dal pannello: qui con la stessa API che usa il pannello).
  const token = await staffToken();
  const queue = await (await fetch(`${API}/v1/admin/reports/queue`, { headers: { Authorization: `Bearer ${token}` } })).json();
  expect(queue.some((item: { target_id: string }) => item.target_id === postId)).toBe(true);
  const decided = await fetch(`${API}/v1/admin/reports/decide`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ target_type: "post", target_id: postId, decision: "hide", ground: "spam" }),
  });
  expect(decided.status).toBe(200);

  // Chi ha pubblicato riceve l'avviso.
  const context = await browser.newContext();
  const author = await context.newPage();
  await login(author, people["giulia.e2e"]!);
  await author.getByRole("button", { name: "Notifiche" }).click();
  await author.getByRole("button", { name: /Un tuo fit è stato nascosto/ }).click();
  const notice = author.getByRole("article", { name: "Fit nascosto" });
  await expect(notice).toContainText(`Il tuo fit «${caption}» è stato nascosto`);
  await expect(notice).toContainText("Motivo: spam.");
  await notice.getByRole("button", { name: "Fai reclamo" }).click();
  await notice.getByRole("textbox", { name: "Il tuo reclamo" }).fill("È un mio outfit vero, non pubblicità.");
  await notice.getByRole("button", { name: "Invia reclamo" }).click();
  await expect(notice).toContainText("Reclamo in esame");
  await expect(notice.getByRole("button", { name: "Fai reclamo" })).toHaveCount(0);
  await context.close();
});
