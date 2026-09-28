import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { E2E_API_PORT } from "../playwright.config";

/**
 * Start the real SAT-SA backend (API + separate worker, SQLite, local
 * storage) with scripts/local_stack.py and wait until it has bootstrapped an
 * organization with administrator, analyst and supervisor credentials.
 */
export const STATE_FILE = path.join(__dirname, ".e2e-state.json");

export default async function globalSetup() {
  const repo = path.resolve(__dirname, "..", "..");
  const dataDir = mkdtempSync(path.join(tmpdir(), "satsa-e2e-"));
  const python = process.env.SATSA_PYTHON ?? (process.platform === "win32" ? "python" : "python3");
  const child = spawn(python, ["scripts/local_stack.py", "--data-dir", dataDir, "--port", String(E2E_API_PORT)], {
    cwd: repo,
    env: { ...process.env, PYTHONPATH: repo },
    stdio: ["ignore", "pipe", "pipe"],
    detached: process.platform !== "win32",
  });
  let output = "";
  child.stdout.on("data", (d) => (output += d));
  child.stderr.on("data", (d) => (output += d));

  const credentialsFile = path.join(dataDir, "credentials.json");
  const deadline = Date.now() + 180_000;
  while (!output.includes("SAT-SA API:")) {
    if (child.exitCode !== null) throw new Error(`local_stack.py exited early:\n${output}`);
    if (Date.now() > deadline) throw new Error(`backend did not start:\n${output}`);
    await new Promise((r) => setTimeout(r, 500));
  }
  if (!existsSync(credentialsFile)) throw new Error("backend started without writing credentials");
  const credentials = JSON.parse(readFileSync(credentialsFile, "utf-8"));
  writeFileSync(STATE_FILE, JSON.stringify({ pid: child.pid, dataDir, repo, credentials }, null, 2));
  child.unref();
}
