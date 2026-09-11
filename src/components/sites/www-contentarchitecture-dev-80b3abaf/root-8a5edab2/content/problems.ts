import type { ProblemsContent } from "../ProblemsSection";

export const problemsContent: ProblemsContent = {
  terminalTitle: "Common problems",
  rows: [
    { num: "001", text: "Agent redesigns the architecture on every prompt", value: "∞ HRS" },
    { num: "002", text: "Page builder schema + section registration + preview", value: "~5 HRS" },
    { num: "003", text: "Draft mode + live preview + webhook revalidation", value: "~4 HRS" },
    { num: "004", text: "CDN vs. data cache — stale content after publish", value: "~3 HRS" },
    { num: "005", text: "Studio structure editors can actually use", value: "~3 HRS" },
    { num: "006", text: "SEO metadata, OG images, sitemaps, robots.txt", value: "~2 HRS" },
    { num: "007", text: "Rewriting the same 12 components", value: "~2 HRS" },
    { num: "008", text: "Redirects, analytics, view transitions, Mux", value: "~2 HRS" },
    { num: "009", text: "Contact form + spam guard + Resend wiring", value: "~1 HR" },
    { num: "010", text: "ESLint, Prettier, Biome, git hooks", value: "~1 HR" },
    { num: "011", text: "Basic auth for staging environments", value: "~1 HR" },
  ],
  summary: "ESTIMATED TIME LOST: ~24 HOURS PER PROJECT  (3 FULL DAYS)",
  heading: "The page builder alone costs you days. Every single time.",
  paragraphs: [
    "It's never the easy stuff that hurts. It's the page builder, modeled from scratch again. Draft mode and live preview, wired up and subtly broken again. The cache bug where published content goes stale and the client swears you shipped something wrong. A Studio structure your editors actually understand, instead of one they email you about. Then the parts that aren't even the CMS: metadata, redirects, spam-guarded forms, the staging password.",
    "This is the part nobody quotes for and everybody rebuilds. Days gone before the real work starts.",
  ],
};
