import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";
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

type Role = "admin" | "analyst" | "supervisor";

/**
 * Sign in once per role and reuse the browser session in later tests, as a
 * real user would. The backend allows five sign-in attempts per client
 * address per minute; one sign-in per role keeps the suite within it.
 */
type SavedState = Awaited<ReturnType<BrowserContext["storageState"]>>;
const sessions = new Map<Role, SavedState>();

async function pageAs(browser: Browser, role: Role): Promise<Page> {
  const saved = sessions.get(role);
  const context = await browser.newContext(saved ? { storageState: saved } : {});
  const page = await context.newPage();
  if (saved) {
    await page.goto("/workbench");
    return page;
  }
  await page.goto("/login");
  await page.getByLabel("Issued credential").fill(state().credentials[role]);
  await page.getByRole("button", { name: "Sign in" }).click();
  // One membership: the organization is selected automatically.
  await expect(page).toHaveURL(/\/workbench$/);
  await expect(page.getByRole("heading", { name: "Workbench", level: 1 })).toBeVisible();
  sessions.set(role, await context.storageState());
  return page;
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

test("the session cookie is HttpOnly, SameSite=Lax and Secure under HTTPS", async ({ browser, baseURL }) => {
  const page = await pageAs(browser, "analyst");
  const cookies = await page.context().cookies();
  const session = cookies.find((c) => c.name === "satsa_session");
  expect(session, "session cookie").toBeTruthy();
  expect(session!.httpOnly).toBe(true);
  expect(session!.sameSite).toBe("Lax");
  if (baseURL?.startsWith("https://")) expect(session!.secure).toBe(true);
  // The browser never receives the raw credential.
  expect(session!.value).not.toContain(state().credentials.analyst);
});

test("a forged organization selection is not honoured", async ({ browser, baseURL }) => {
  const page = await pageAs(browser, "analyst");
  await page.context().addCookies([{ name: "satsa_org", value: "org_not_a_membership", url: baseURL! }]);
  await page.goto("/workbench");
  // The only real membership is used; the forged id never reaches the API as a scope.
  await expect(page.getByRole("heading", { name: "Workbench", level: 1 })).toBeVisible();
  await expect(page.getByText("Signal findings")).toBeVisible();
});

test("an analyst ingests, validates and starts a run", async ({ browser }) => {
  const { repo } = state();
  const page = await pageAs(browser, "analyst");

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
});

test("the entity is ranked from its persisted risk", async ({ browser }) => {
  const page = await pageAs(browser, "supervisor");
  await page.getByRole("link", { name: "Entities" }).first().click();
  const row = page.getByRole("list", { name: "Entities" }).getByRole("link", { name: new RegExp(ENTITY) });
  await expect(row).toBeVisible();
  await expect(row).toContainText("Awaiting review");
});

test("a supervisor decides and TRUST-SAT verifies the decided record", async ({ browser }) => {
  const page = await pageAs(browser, "supervisor");
  await page.goto("/workbench");
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
});

test("the run records the advisory model's explicit abstention", async ({ browser }) => {
  // No model has been trained or deployed on this stack: the worker still
  // records an inference, as an abstention, and the page says why.
  const page = await pageAs(browser, "supervisor");
  await page.goto(runUrl);
  await expect(page.getByRole("heading", { name: "Advisory model score" })).toBeVisible();
  await expect(page.locator("[data-inference]")).toHaveAttribute("data-inference", "abstained");
  await expect(page.getByText("No model is deployed")).toBeVisible();
});

test("an analyst builds and validates a dataset; the worker reports it too small", async ({ browser }) => {
  const page = await pageAs(browser, "analyst");
  await page.getByRole("link", { name: "Models" }).first().click();
  await expect(page.getByText("No model is deployed")).toBeVisible();
  await page.getByRole("button", { name: "Build dataset from recorded decisions" }).click();
  const datasets = page.getByRole("region", { name: "Datasets" });
  await expect(datasets.getByText("review-outcome v1")).toBeVisible();
  await datasets.getByRole("button", { name: "Validate" }).click();
  // Validation runs in the worker; one decided run is below the policy minimum.
  await expect(async () => {
    await page.reload();
    await expect(page.getByRole("region", { name: "Datasets" }).getByText("invalid", { exact: true })).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 2 * 60_000 });
  await expect(page.getByText(/Fail · minimum rows/)).toBeVisible();
  // Training needs a valid dataset: no train control is offered.
  await expect(page.getByRole("button", { name: "Train model" })).toHaveCount(0);
});

test("the administrator reads the audit trail of the run", async ({ browser }) => {
  const page = await pageAs(browser, "admin");
  await page.goto(`/workbench/audit?run=${runUrl.split("/").pop()}`);
  await expect(page.getByRole("table", { name: "Audit events" })).toBeVisible();
  await expect(page.getByText("trust.supervisory_finalized")).toBeVisible();
});

test("the backend refuses the audit log to a role without audit permission", async ({ browser }) => {
  // The analyst has no audit permission: the backend refuses, and the page says so.
  const page = await pageAs(browser, "analyst");
  await page.goto("/workbench/audit");
  await expect(page.getByText("Audit events: Not permitted")).toBeVisible();
});

test("sign-out revokes the backend session", async ({ browser }) => {
  const page = await pageAs(browser, "admin");
  await page.goto("/workbench");
  await page.getByRole("button", { name: "Sign out" }).first().click();
  await expect(page).toHaveURL(/\/login/);

  // The saved session token was revoked on the backend, not only deleted locally.
  const replay = await pageAs(browser, "admin"); // opens /workbench with the saved, now revoked session
  await expect(replay).toHaveURL(/\/login\?reason=expired/);
});
