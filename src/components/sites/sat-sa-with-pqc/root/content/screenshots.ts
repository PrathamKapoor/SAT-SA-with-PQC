export const screenshotsContent = {
  eyebrow: "The product",
  title: "Real pages, real demo data.",
  intro:
    "Every screenshot below is the SAT-SA Supervisory Workbench running on its demo assessment, not mockups.",
  items: [
    {
      src: "/sites/sat-sa-with-pqc/root/screenshots/workbench.jpeg",
      alt: "SAT-SA Workbench: six workflow cards, the next review item, the supervisory SOP and a capability overview",
      caption: "Workbench: choose the workflow, see what needs attention.",
    },
    {
      src: "/sites/sat-sa-with-pqc/root/screenshots/entity-detail.jpeg",
      alt: "CSE-X entity detail: top supervisory concerns, score decomposition and the eight-dimension capability scorecard",
      caption: "Entity detail: concerns, score decomposition and capabilities.",
    },
    {
      src: "/sites/sat-sa-with-pqc/root/screenshots/finding-detail.jpeg",
      alt: "Finding detail for critical alerts closed without escalation: observed pattern, statutory baseline, peer context and timeline",
      caption: "Finding detail: pattern, why it matters, peer context, timeline.",
    },
    {
      src: "/sites/sat-sa-with-pqc/root/screenshots/analytics.jpeg",
      alt: "SAT-SA Analytics page: cross-entity capability overview and cohort comparability criteria",
      caption: "Analytics: capabilities, trends and cohort benchmarks.",
    },
  ],
} as const;
