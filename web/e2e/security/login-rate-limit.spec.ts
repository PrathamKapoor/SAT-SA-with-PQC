import { expect, test } from "@playwright/test";

/**
 * Login attempts are limited per browser address (5 per minute) through the
 * real proxy chain: Caddy -> web -> API. A client that rotates a forged
 * X-Forwarded-For header must still be limited, because Caddy replaces the
 * header with the connection's address and the API trusts it only from the
 * web tier.
 *
 * Run separately (it locks this address out of sign-in for a minute):
 *   SATSA_E2E_SUITE=security npm run test:e2e
 */
test("forged X-Forwarded-For does not bypass the login limit", async ({ page }) => {
  // The API counts attempts in fixed one-minute windows; earlier sign-ins
  // from this address may have used part of the current one. Start fresh.
  await page.waitForTimeout(60_000 - (Date.now() % 60_000) + 1_000);
  const outcomes: string[] = [];
  for (let attempt = 0; attempt < 7; attempt++) {
    await page.setExtraHTTPHeaders({ "X-Forwarded-For": `203.0.113.${attempt + 1}` });
    await page.goto("/login");
    await page.getByLabel("Issued credential").fill(`not-a-credential-${attempt}`);
    await page.getByRole("button", { name: /sign in/i }).click();
    const alert = page.locator("#credential-error");
    await expect(alert).toBeVisible();
    outcomes.push((await alert.textContent()) ?? "");
  }
  expect(outcomes.slice(0, 5).every((text) => text.includes("Credential not recognised"))).toBe(true);
  expect(outcomes.slice(5).every((text) => text.includes("Too many requests"))).toBe(true);
});
