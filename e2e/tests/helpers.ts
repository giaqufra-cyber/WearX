import { expect, type Page } from "@playwright/test";

export const AUTH = "http://localhost:54321";
export const API = "http://localhost:8000";

export type Person = { id: string; nickname: string; email: string; password: string };
export type State = { people: Record<string, Person>; posts: string[] };

export async function state(): Promise<State> {
  return (await fetch(`${AUTH}/__e2e/state`)).json() as Promise<State>;
}

/** Il servizio delle password violate è esterno: nei test risponde "nessuna corrispondenza". */
export async function offlineServices(page: Page): Promise<void> {
  await page.route("https://api.pwnedpasswords.com/**", (route) =>
    route.fulfill({ status: 200, contentType: "text/plain", body: "" }),
  );
}

export async function login(page: Page, person: Pick<Person, "email" | "password">): Promise<void> {
  await offlineServices(page);
  await page.goto("/login");
  await page.getByRole("textbox", { name: "EMAIL" }).fill(person.email);
  await page.getByRole("textbox", { name: "PASSWORD" }).fill(person.password);
  await page.getByRole("button", { name: "Accedi" }).click();
  await expect(page).toHaveURL(/\/(feed)?$/);
}

/** Il lavoro orario che pubblica media e numero dei voti (seduta 22), lanciato subito. */
export async function publishVotes(): Promise<void> {
  await fetch(`${AUTH}/__e2e/publish`, { method: "POST" });
}

export async function staffToken(): Promise<string> {
  const body = (await (await fetch(`${AUTH}/__e2e/staff-token`, { method: "POST" })).json()) as { access_token: string };
  return body.access_token;
}

export function unique(prefix: string): string {
  return `${prefix}${Date.now().toString(36).slice(-5)}`;
}
