#!/usr/bin/env node
// Downloads contentarchitecture.dev assets not already present into the page/site namespaces.
// Usage: node scripts/download-assets-www-contentarchitecture-dev-80b3abaf-root-8a5edab2.mjs
import fs from "node:fs/promises";
import path from "node:path";

const PAGE = "public/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2";
const SHARED = "public/sites/www-contentarchitecture-dev-80b3abaf/shared";
const SANITY = "https://cdn.sanity.io/images/szlvuc1t/production";

const ASSETS = [
  { url: `${SANITY}/db451abc27a16f698305dcb56ec920d5a9dc08c8-1566x1566.jpg?w=200&h=200&fit=crop&q=85&fm=jpg`, out: `${PAGE}/avatars/maintainer.jpg` },
  { url: "https://github.com/GoodFellaStudio.png?size=64", out: `${PAGE}/avatars/trusted-goodfellastudio.png` },
  { url: "https://github.com/MinhChanh6.png?size=64", out: `${PAGE}/avatars/trusted-minhchanh6.png` },
  { url: "https://github.com/elliottmangham.png?size=64", out: `${PAGE}/avatars/trusted-elliottmangham.png` },
  { url: "https://github.com/malikkotb.png?size=64", out: `${PAGE}/avatars/trusted-malikkotb.png` },
  { url: "https://github.com/studioboldest.png?size=64", out: `${PAGE}/avatars/trusted-studioboldest.png` },
  // /favicon.ico on the origin returned HTTP 500 on 2026-09-11; the light/dark PNG icons cover it.
  { url: `${SANITY}/c40bf16727173bad99888c2bfb3f2e69b92a62fc-800x800.png?w=64&h=64&fm=png&q=85&fit=crop`, out: `${SHARED}/seo/icon-light.png` },
  { url: `${SANITY}/fb5bfe82806b22de4ae481600887a65458496e5b-800x800.png?w=64&h=64&fm=png&q=85&fit=crop`, out: `${SHARED}/seo/icon-dark.png` },
  { url: `${SANITY}/fa6b9eeac8902bc3b2f665b561ad188d9401256f-1920x1008.png?w=1200&h=630&q=85&fit=crop&fm=png`, out: `${SHARED}/seo/og-image.png` },
];

async function download({ url, out }) {
  try {
    await fs.access(out);
    return `skip  ${out}`;
  } catch {
    // not present yet
  }
  const res = await fetch(url, { redirect: "follow" });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  const type = res.headers.get("content-type") ?? "";
  if (!/^image\//.test(type) && !/icon/.test(type)) throw new Error(`unexpected content-type ${type} for ${url}`);
  await fs.mkdir(path.dirname(out), { recursive: true });
  await fs.writeFile(out, Buffer.from(await res.arrayBuffer()));
  return `ok    ${out}`;
}

const queue = [...ASSETS];
const failures = [];
async function worker() {
  for (let item = queue.shift(); item; item = queue.shift()) {
    try {
      console.log(await download(item));
    } catch (err) {
      failures.push(item.out);
      console.error(`FAIL  ${item.out}: ${err instanceof Error ? err.message : err}`);
    }
  }
}
await Promise.all(Array.from({ length: 4 }, worker));
if (failures.length) process.exitCode = 1;
