import assert from "node:assert/strict";
import test from "node:test";

const baseUrl = process.env.SAT_SA_BASE_URL ?? "http://localhost:3001";

async function getHtml(pathname) {
  const response = await fetch(`${baseUrl}${pathname}`);
  assert.equal(response.status, 200, `${pathname} should render successfully`);
  return response.text();
}

test("overview exposes one primary review action and readable navigation", async () => {
  const html = await getHtml("/workbench/overview");

  assert.match(html, /data-theme="satsa-light"/);
  assert.match(html, /data-grainient-mode="light"/);
  assert.equal((html.match(/Open Review Queue/g) ?? []).length, 1);
  assert.match(html, /AIR-GAPPED · READY/i);
  assert.match(html, /Trends &amp; Benchmarks/);
  assert.match(html, /Governance &amp; Audit/);
  assert.match(html, /Administration/);
  assert.match(html, />Dimension</);
  assert.match(html, />Index</);
  assert.doesNotMatch(html, /Capacity Index/);
  assert.equal((html.match(/HIGH CONFIDENCE/g) ?? []).length, 3);
});

test("landing hero keeps an accessible headline and decorative evidence flow", async () => {
  const html = await getHtml("/");

  assert.match(html, /data-theme="satsa-light"/);
  assert.match(html, /data-grainient-mode="light"/);
  assert.match(html, /<h1[^>]*>[\s\S]*Supervision, backed by evidence\./);
  assert.match(html, /data-evidence-flow="true"[^>]*aria-hidden="true"/);
});
