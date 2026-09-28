// Smoke tests against a running web server (no session needed):
//   SAT_SA_BASE_URL=http://localhost:3000 npm run test:ui
// The authenticated workflow is covered by the browser end-to-end test (npm run test:e2e).
import assert from "node:assert/strict";
import test from "node:test";

const base = process.env.SAT_SA_BASE_URL ?? "http://localhost:3000";
const get = (path, init = {}) => fetch(`${base}${path}`, { redirect: "manual", ...init });

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

test("an invalid session is cleared and sent to sign-in", async () => {
  const res = await get("/workbench", { headers: { cookie: "satsa_session=not-a-session" } });
  assert.equal(res.status, 307);
  assert.match(res.headers.get("location") ?? "", /\/logout\?reason=expired$/);
  const cleared = await get("/logout?reason=expired");
  assert.equal(cleared.status, 307);
  assert.match(cleared.headers.get("set-cookie") ?? "", /satsa_session=;/);
});

test("sign-in asks only for an issued credential", async () => {
  const html = await (await get("/login")).text();
  assert.match(html, /Issued credential/);
  assert.doesNotMatch(html, /Development session|dev-admin|development identity/i, "no frontend-only identities");
});
