import { execSync } from "node:child_process";
import { existsSync, readFileSync, rmSync } from "node:fs";
import path from "node:path";

const STATE_FILE = path.join(__dirname, ".e2e-state.json");

/** Stop the backend started by global-setup (the launcher and its API and worker children). */
export default async function globalTeardown() {
  if (!existsSync(STATE_FILE)) return;
  const { pid } = JSON.parse(readFileSync(STATE_FILE, "utf-8")) as { pid: number | null };
  if (!pid) {
    rmSync(STATE_FILE, { force: true });
    return; // a deployed stack: nothing was started
  }
  try {
    if (process.platform === "win32") execSync(`taskkill /PID ${pid} /T /F`, { stdio: "ignore" });
    else process.kill(-pid, "SIGTERM");
  } catch {
    /* already stopped */
  }
  rmSync(STATE_FILE, { force: true });
}
