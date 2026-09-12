export const screenshotsContent = {
  eyebrow: "The product",
  title: "Real pages, real demo data.",
  intro:
    "Every screenshot below is the actual FastAPI dashboard, captured from a live run of the committed demo dataset — not mockups.",
  items: [
    {
      src: "/sites/sat-sa-with-pqc/root/screenshots/overview.jpeg",
      alt: "SAT-SA Overview page: entity risk roster ranked by supervisory risk, with a trust-verified banner",
      caption: "Overview — who needs attention, ranked by risk.",
    },
    {
      src: "/sites/sat-sa-with-pqc/root/screenshots/entity-detail.jpeg",
      alt: "ACME-BANK entity detail page: risk decomposition by dimension, assessment period coverage, and signal findings table",
      caption: "Entity detail — risk decomposition, evidence, and rationale.",
    },
    {
      src: "/sites/sat-sa-with-pqc/root/screenshots/finding-detail.jpeg",
      alt: "Finding detail page for execution_gap.ack_without_investigation, showing why it fired, its evidence, a bounded recommendation, and trust verification",
      caption: "Finding detail — WHAT / WHY / EVIDENCE / TRUST, in one page.",
    },
    {
      src: "/sites/sat-sa-with-pqc/root/screenshots/architecture.jpeg",
      alt: "SAT-SA architecture page showing the full pipeline diagram and the 32-agent roster",
      caption: "Architecture — the same diagram this page reuses, live and clickable.",
    },
  ],
} as const;
