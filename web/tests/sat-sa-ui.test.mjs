// Smoke tests against a running dev server (development auth adapter, fixture data):
//   SAT_SA_BASE_URL=http://localhost:3000 npm run test:ui
import assert from "node:assert/strict";
import test from "node:test";

const base = process.env.SAT_SA_BASE_URL ?? "http://localhost:3000";
const get = (path, init = {}) => fetch(`${base}${path}`, { redirect: "manual", ...init });
const text = async (path, init) => (await get(path, init)).text();

const ROLE = {
  "dev-admin": "satsa_admin",
  "dev-supervisor": "satsa_supervisor",
  "dev-analyst": "satsa_analyst",
  "dev-auditor": "satsa_auditor",
  "dev-viewer": "satsa_viewer",
};
/** The same browser-session cookie the development adapter writes. */
const devCookie = (principal, role = ROLE[principal]) =>
  Buffer.from(
    JSON.stringify({ marker: "satsa-development-session/v1", principal, role, displayName: principal, startedAt: Date.now() }),
    "utf8",
  ).toString("base64url");
const as = (principal, role) => ({ headers: { cookie: `satsa_dev_session=${devCookie(principal, role)}` } });

const hrefs = (html) => new Set([...html.matchAll(/href="(\/workbench[^"#?]*)"/g)].map((m) => m[1]));

test("public pages render without supervisory data or em dashes", async () => {
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

test("sign-in explains the development environment and lists every development identity", async () => {
  const html = await text("/login");
  assert.match(html, /Backend authentication is not connected in this local development environment/);
  for (const p of Object.keys(ROLE)) assert.match(html, new RegExp(`value="${p}"`), p);
  assert.doesNotMatch(html, /Issued credential/, "no dead-end credential form in development mode");
});

test("a tampered development session is rejected", async () => {
  const forged = await get("/workbench", as("dev-viewer", "satsa_admin"));
  assert.equal(forged.status, 307);
  const unknown = await get("/workbench", as("dev-root", "satsa_admin"));
  assert.equal(unknown.status, 307);
});

test("the top bar labels the development session", async () => {
  const html = await text("/workbench", as("dev-supervisor"));
  assert.match(html, /Development session/);
  assert.match(html, /dev-supervisor/);
  assert.match(html, /Exit development session/);
  assert.match(html, /Development fixture/);
});

/** Navigation per role follows the existing permissions (qsmlops satsa_* roles). */
const EXPECT = {
  "dev-admin": { has: ["entities", "findings", "review-queue", "analytics", "agents", "trust", "audit", "admin", "system", "reports", "ingest"], lacks: [] },
  "dev-supervisor": { has: ["entities", "findings", "review-queue", "decisions", "analytics", "benchmarks", "agents", "trust", "reports"], lacks: ["audit", "admin", "system"] },
  "dev-analyst": { has: ["entities", "findings", "ingest", "submissions", "analytics", "pipeline", "agents", "reports"], lacks: ["audit", "admin", "system"] },
  "dev-auditor": { has: ["findings", "security-data", "trust", "audit", "reports"], lacks: ["ingest", "admin", "system"] },
  "dev-viewer": { has: ["findings", "entities", "trust", "reports"], lacks: ["ingest", "audit", "admin", "system"] },
};

for (const [principal, { has, lacks }] of Object.entries(EXPECT)) {
  test(`navigation for ${principal}`, async () => {
    const links = hrefs(await text("/workbench", as(principal)));
    for (const r of has) assert.ok(links.has(`/workbench/${r}`), `${principal} should see ${r}`);
    for (const r of lacks) assert.ok(!links.has(`/workbench/${r}`), `${principal} should not see ${r}`);
  });
}

test("every development identity lands on the same Workbench", async () => {
  const login = await text("/login");
  assert.doesNotMatch(login, /name="next"/, "sign-in must not carry a per-role destination");
  for (const p of Object.keys(ROLE)) {
    const res = await get("/workbench", as(p));
    assert.equal(res.status, 200, p);
    const html = await res.text();
    assert.match(html, /Supervisory intelligence\./, p);
    for (const tile of ["Entities", "Findings", "Review queue", "Analytics", "TRUST-SAT"]) assert.match(html, new RegExp(`>${tile}<`), `${p}: ${tile} tile`);
    assert.match(html, /Capability overview/, p);
  }
});

test("the SAT-SA identity returns to the public site", async () => {
  const html = await text("/workbench", as("dev-analyst"));
  assert.match(html, /<a[^>]*href="\/"[^>]*title="Return to SAT-SA public site"|<a[^>]*title="Return to SAT-SA public site"[^>]*href="\/"/);
});

test("capability overview never invents a score", async () => {
  const html = await text("/workbench", as("dev-viewer"));
  assert.match(html, /Not assessed/);
  for (const n of ["82", "72", "75", "85", "79", "87", "77", "84"]) assert.doesNotMatch(html, new RegExp(`>${n}<`), `no legacy capability score ${n}`);
});

test("role gates hold on direct URLs", async () => {
  assert.match(await text("/workbench/admin", as("dev-viewer")), /requires the administrator role/);
  assert.match(await text("/workbench/audit", as("dev-analyst")), /requires the auditor or administrator role/);
  assert.match(await text("/workbench/ingest", as("dev-auditor")), /Your role cannot ingest submissions/);
  assert.match(await text("/workbench/review-queue", as("dev-viewer")), /cannot record a decision/);
});

test("every application route renders for the development administrator", async () => {
  const routes = [
    "", "overview", "entities", "findings", "review-queue", "decisions", "analytics", "benchmarks", "pipeline",
    "submissions", "ingest", "security-data", "agents", "architecture", "reports", "trust", "audit", "admin", "system",
  ];
  for (const r of routes) {
    const res = await get(`/workbench${r ? `/${r}` : ""}`, as("dev-admin"));
    assert.equal(res.status, 200, r || "workbench");
  }
});
