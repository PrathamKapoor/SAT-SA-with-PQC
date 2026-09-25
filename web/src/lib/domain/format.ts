const DATE = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" });
const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
  timeZone: "UTC",
});
const TIME = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23", timeZone: "UTC" });

export const fmtDate = (ts: number | null | undefined) => (ts ? DATE.format(ts * 1000) : "Not recorded");
export const fmtDateTime = (ts: number | null | undefined) => (ts ? `${DATE_TIME.format(ts * 1000)} UTC` : "Not recorded");
export const fmtTime = (ts: number | null | undefined) => (ts ? TIME.format(ts * 1000) : "");

export function fmtPeriod(start: number, end: number): string {
  return `${DATE.format(start * 1000)} to ${DATE.format(end * 1000)}`;
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return "Not recorded";
  const s = Math.round(Math.abs(seconds));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${s % 60 ? `${s % 60}s` : ""}`.trim();
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.round((s % 3600) / 60)}m`;
  return `${Math.floor(s / 86400)}d ${Math.round((s % 86400) / 3600)}h`;
}

export const fmtPct = (v: number | null | undefined, digits = 0) =>
  v == null || !Number.isFinite(v) ? "n/a" : `${(v * 100).toFixed(digits)}%`;

export const fmtNum = (v: number | null | undefined, digits = 1) =>
  v == null || !Number.isFinite(v) ? "n/a" : Number.isInteger(v) ? String(v) : v.toFixed(digits);

/**
 * Backend prose (rationales, limitations, recommendation reasons, agent
 * purposes) is displayed verbatim except for punctuation: em and en dashes
 * used as separators become a colon or comma so no em dash reaches the UI.
 */
export function prose(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .replace(/\s+[—–]\s+/g, ": ")
    .replace(/[—]/g, ", ")
    .replace(/(\w)–(\w)/g, "$1-$2")
    .replace(/:\s*:/g, ":");
}

export const shortDigest =(hex: string | null | undefined, n = 12) => (hex ? `${hex.slice(0, n)}` : "none");

export const shortId = (id: string) => {
  const [kind, rest] = id.split(/_(.+)/);
  return rest ? `${kind}·${rest.slice(0, 6)}` : id.slice(0, 10);
};

export function relativeAge(ts: number, now = Date.now() / 1000): string {
  const d = now - ts;
  if (d < 90) return "just now";
  if (d < 3600) return `${Math.round(d / 60)} min ago`;
  if (d < 86400) return `${Math.round(d / 3600)} h ago`;
  return `${Math.round(d / 86400)} d ago`;
}

/** "directory:docs/demo/submissions/CSE-EXEC" (either slash) -> "CSE-EXEC submission" */
export function sourceName(sourceSystem: string): string {
  const [kind, path = ""] = sourceSystem.includes(":") ? sourceSystem.split(/:(.+)/) : ["", sourceSystem];
  const leaf = path.split(/[\\/]/).filter(Boolean).pop() ?? path;
  return kind === "directory" ? `${leaf} submission` : leaf || sourceSystem;
}
