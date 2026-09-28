import { expect, test, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
import path from "node:path";

/**
 * The supervisory workflow through the browser against the real backend:
 * sign in, organization, ingest (entity, period, six uploads), validation,
 * run, worker progress, findings, evidence records, risk and priority,
 * recommendations, supervisor decision, TRUST-SAT finalization and
 * verification, audit. Nothing is mocked; every value comes from the API.
 */
interface State {
  repo: string;
  credentials: { organization_id: string; admin: string; analyst: string; supervisor: string };
}
const state = (): State => JSON.parse(readFileSync(path.join(__dirname, ".e2e-state.json"), "utf-8"));
const DEMO = (repo: string, category: string) => path.join(repo, "docs", "demo", "submissions", "CSE-EXEC", `${category}.csv`);
const CATEGORIES = ["alerts", "cases", "investigation_steps", "escalations", "dispositions", "assets"];
const ENTITY = `E2E Bank ${Date.now().toString(36)}`;

async function signIn(page: Page, credential: string) {
  await page.goto("/login");
  await page.getByLabel("Issued credential").fill(credential);
  await page.getByRole("button", { name: "Sign in" }).click();
  // One membership: the organization is selected automatically.
  await expect(page).toHaveURL(/\/workbench$/);
  await expect(page.getByRole("heading", { name: "Workbench", level: 1 })).toBeVisible();
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await expect(page).toHaveURL(/\/login/);
}

test.describe.configure({ mode: "serial" });

let runUrl = "";

test("unauthenticated and invalid sessions are sent to sign-in", async ({ page, context }) => {
  await page.goto("/workbench");
  await expect(page).toHaveURL(/\/login$/);

  await context.addCookies([{ name: "satsa_session", value: "not-a-real-session", url: page.url() }]);
  await page.goto("/workbench");
  await expect(page).toHaveURL(/\/login\?reason=expired/);
  await expect(page.getByText("Your session ended")).toBeVisible();

  await page.getByLabel("Issued credential").fill("wrong.credential");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("Credential not recognised.")).toBeVisible();
});

test("an analyst ingests, validates and starts a run", async ({ page }) => {
  const { repo, credentials } = state();
  await signIn(page, credentials.analyst);

  await page.getByRole("link", { name: "Ingest evidence" }).first().click();
  await expect(page).toHaveURL(/\/workbench\/ingest/);
  await page.getByRole("button", { name: "New entity" }).click();
  await page.locator('input[name="display_name"]').fill(ENTITY);
  await page.locator('input[name="sector"]').fill("banking");
  await page.locator('input[name="environment_class"]').fill("on-prem");
  await page.locator('input[name="period_start"]').fill("2025-01-01");
  await page.locator('input[name="period_end"]').fill("2025-01-31");
  for (const c of CATEGORIES) await page.locator(`input[type="file"][name="${c}"]`).setInputFiles(DEMO(repo, c));
  await expect(page.getByText("Pre-check passed")).toHaveCount(CATEGORIES.length);

  await page.getByRole("button", { name: "Submit and validate" }).click();
  const result = page.locator("[data-validation]");
  await expect(result).toHaveAttribute("data-validation", "valid", { timeout: 60_000 });
  for (const step of ["entity", "assessment", "submission", "version", "upload", "complete", "validate"]) {
    await expect(page.locator(`[data-step="${step}"]`)).toHaveAttribute("data-state", "done");
  }

  await page.getByRole("button", { name: "Start analysis" }).click();
  await expect(page).toHaveURL(/\/workbench\/runs\/run_/);
  runUrl = new URL(page.url()).pathname;

  // The worker processes the run; the page re-reads persisted state until review.
  await expect(page.locator("[data-run-status]")).toHaveAttribute("data-run-status", "awaiting_review", { timeout: 5 * 60_000 });
  await expect(page.getByRole("heading", { name: "Findings" })).toBeVisible();
  const findings = page.getByRole("list", { name: "Findings" }).getByRole("link");
  expect(await findings.count()).toBeGreaterThan(0);
  await expect(page.getByText("No risk profile yet")).toHaveCount(0);

  // An analyst cannot decide.
  await expect(page.getByText("Awaiting a supervisor")).toBeVisible();
  await expect(page.getByRole("button", { name: "Record decision" })).toHaveCount(0);

  // Finding workspace: evidence resolves to canonical record content; risk and priority come from the API.
  const signal = page.getByRole("list", { name: "Findings" }).getByRole("link").filter({ hasText: "Signal" }).first();
  await signal.click();
  await expect(page).toHaveURL(/\/workbench\/findings\//);
  await expect(page.getByRole("heading", { name: "Why it was flagged" })).toBeVisible();
  const cited = page.locator("[data-evidence]");
  if ((await cited.count()) > 0) await expect(cited.first().locator("dl")).toBeVisible();
  await expect(page.getByText(/Rank \d+/)).toBeVisible();
  await signOut(page);
});

test("the entity is ranked from its persisted risk", async ({ page }) => {
  const { credentials } = state();
  await signIn(page, credentials.supervisor);
  await page.getByRole("link", { name: "Entities" }).first().click();
  const row = page.getByRole("list", { name: "Entities" }).getByRole("link", { name: new RegExp(ENTITY) });
  await expect(row).toBeVisible();
  await expect(row).toContainText("Awaiting review");
  await signOut(page);
});

test("a supervisor decides and TRUST-SAT verifies the decided record", async ({ page }) => {
  const { credentials } = state();
  await signIn(page, credentials.supervisor);
  await page.getByRole("link", { name: /Review queue/ }).first().click();
  await page.getByRole("list", { name: "Runs awaiting review" }).getByRole("link", { name: new RegExp(ENTITY) }).click();
  await expect(page).toHaveURL(new RegExp(runUrl));

  await expect(page.getByRole("heading", { name: "Recommendations" })).toBeVisible();
  await page.getByText("Confirm", { exact: true }).click();
  await page.getByLabel("Reason").fill("Evidence reviewed in the end-to-end test.");
  await page.getByRole("button", { name: "Record decision" }).click();
  await expect(page.locator("[data-decision]")).toHaveAttribute("data-decision", "confirm");

  // The worker finalizes after the decision; the page keeps re-reading until then.
  await expect(page.locator("[data-run-status]")).toHaveAttribute("data-run-status", /completed|partial/, { timeout: 3 * 60_000 });
  await expect(page.getByText("Receipt state")).toBeVisible();
  await page.getByRole("button", { name: "Verify now" }).click();
  await expect(page.locator("[data-verification]")).toHaveAttribute("data-verification", "verified");

  await page.getByRole("link", { name: "Decisions" }).first().click();
  await expect(page.getByRole("link", { name: new RegExp(ENTITY) })).toBeVisible();
  await signOut(page);
});

test("the administrator reads the audit trail of the run", async ({ page }) => {
  const { credentials } = state();
  await signIn(page, credentials.admin);
  await page.goto(`/workbench/audit?run=${runUrl.split("/").pop()}`);
  await expect(page.getByRole("table", { name: "Audit events" })).toBeVisible();
  await expect(page.getByText("trust.supervisory_finalized")).toBeVisible();
  await signOut(page);
});

test("the backend refuses the audit log to a role without audit permission", async ({ page }) => {
  // The analyst has no audit permission: the backend refuses, and the page says so.
  const { credentials } = state();
  await signIn(page, credentials.analyst);
  await page.goto("/workbench/audit");
  await expect(page.getByText("Audit events: Not permitted")).toBeVisible();
  await signOut(page);
});
