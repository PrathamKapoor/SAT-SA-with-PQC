// Smoke tests against a running server: SAT_SA_BASE_URL=http://localhost:3000 npm run test:ui
// Fixture mode (default) is assumed for the development-session checks.
import assert from "node:assert/strict";
import test from "node:test";

const base = process.env.SAT_SA_BASE_URL ?? "http://localhost:3000";
const get = (path, init = {}) => fetch(`${base}${path}`, { redirect: "manual", ...init });
const text = async (path, init) => (await get(path, init)).text();
const asRole = (role) => ({ headers: { cookie: `satsa_dev_role=${role}` } });

test("public pages render without supervisory data", async () => {
  for (const path of ["/", "/methodology", "/security"]) {
    const res = await get(path);
    assert.equal(res.status, 200, path);
    const html = await res.text();
    assert.doesNotMatch(html, /finding_[a-f0-9]{8}|entity_[a-f0-9]{8}/, `${path} must not expose record ids`);
    assert.doesNotMatch(html.replace(/<script[\s\S]*?<\/script>/g, ""), /—/, `${path} must not contain em dashes`);
  }
});

test("the application requires a session", async () => {
  const res = await get("/workbench");
  assert.equal(res.status, 307);
  assert.match(res.headers.get("location") ?? "", /\/login$/);
});

test("sign-in offers a credential form and a labelled development session", async () => {
  const html = await text("/login");
  assert.match(html, /Issued credential/);
  assert.match(html, /Development session/);
  assert.match(html, /Nothing is verified/);
});

test("workbench shows the data origin and the attention queue", async () => {
  const html = await text("/workbench", asRole("satsa_supervisor"));
  assert.match(html, /Development fixture/);
  assert.match(html, /Attention queue/);
  assert.match(html, /Entities by priority/);
});

test("role gates hide administration from viewers", async () => {
  const nav = await text("/workbench", asRole("satsa_viewer"));
  assert.doesNotMatch(nav, /href="\/workbench\/admin"/);
  const admin = await text("/workbench/admin", asRole("satsa_viewer"));
  assert.match(admin, /requires the administrator role/);
});

test("every application route renders for an administrator", async () => {
  const routes = [
    "overview", "entities", "findings", "review-queue", "decisions", "analytics", "benchmarks", "pipeline",
    "submissions", "ingest", "security-data", "agents", "architecture", "reports", "trust", "audit", "admin", "system",
  ];
  for (const r of routes) {
    const res = await get(`/workbench/${r}`, asRole("satsa_admin"));
    assert.equal(res.status, 200, r);
  }
});
