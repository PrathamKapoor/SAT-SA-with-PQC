import type { LearnMoreContent } from "../LearnMore";

const PORTRAIT = {
  src: "/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/avatars/maintainer.jpg",
  alt: "Man in black turtleneck smiling and looking to the side indoors",
};

const BLOG = "https://www.edoardolunardi.dev/blog";

/**
 * CA README drawer. Labels, headings, links and the portrait are taken from
 * `dom/12-readme-drawer.html`; the paragraph copy is a condensed paraphrase of the live essay
 * (same structure: 6 / 5 / 2 paragraphs, links and portrait in the same positions), not a
 * verbatim transcript.
 */
export const learnMoreContent: LearnMoreContent = {
  trigger: "Learn more",
  title: "README ╱ The content architecture",
  subtitle: "A personal note from the maintainer",
  close: "Close",
  tocLabel: "Sections",
  sections: [
    {
      id: "why-this-exists",
      number: "001",
      title: "Why this exists",
      paragraphs: [
        [
          "Every new Sanity build began with the same week of groundwork: a framework, the Studio, a page builder, an SEO layer, webhook revalidation and yet another contact form, all rebuilt from zero.",
        ],
        ["That groundwork used up days of the budget before the client saw anything that mattered to them."],
        [
          "So the fixes started collecting in one boilerplate, one project after another. Every production incident, from broken migrations to stale caches and duplicate webhooks, ended up patched there.",
        ],
        [
          "For years that repetition passed for expertise. It was really just the same foundation, built again.",
        ],
        ["Eventually there was no good reason to keep it private."],
        [
          "The reasoning behind the codebase is written up in four free articles: ",
          { text: "CMS structure", href: `${BLOG}/the-content-architecture-cms-structure` },
          ", ",
          { text: "content models", href: `${BLOG}/the-content-architecture-content-models` },
          ", ",
          { text: "page composition", href: `${BLOG}/the-content-architecture-page-composition` },
          ", and ",
          { text: "content primitives", href: `${BLOG}/the-content-architecture-content-primitives` },
          ".",
        ],
      ],
    },
    {
      id: "why-i-keep-shipping-it",
      number: "002",
      title: "Why I keep shipping it",
      paragraphs: [
        ["It runs on every one of my own projects, so a bug found in client work lands here as a fix days later."],
        [
          "One maintainer keeps the architecture consistent, from the first schema file to the last revalidation hook, without opinions pulling it in different directions.",
        ],
        [
          "The repo is the same code I ship on paid work, under the same deadlines. It is not a demo polished for a sale.",
        ],
        [
          "There is no subscription product behind it and nothing phones home. A purchase means the code is yours, and new features come from what real client projects turn up.",
        ],
        [
          "Paying users keep me honest about framework and Sanity upgrades, and the decisions are written down, which is exactly what lets an agent build within them instead of guessing.",
        ],
      ],
    },
    {
      id: "who-am-i",
      number: "003",
      title: "Who am I",
      paragraphs: [
        [
          "I am Edo ",
          { image: PORTRAIT },
          " - a creative web engineer with close to ten years of work for international brands and industry awards. Based in Vienna, working worldwide.",
        ],
        [
          "I'm on ",
          { text: "Instagram", href: "https://www.instagram.com/edo.tsx" },
          ", ",
          { text: "LinkedIn", href: "https://www.linkedin.com/in/edoardolunardi" },
          " and ",
          { text: "X", href: "https://x.com/edo_lunardi" },
          "; portfolio at ",
          { text: "edoardolunardi.dev", href: "https://www.edoardolunardi.dev/" },
          ", email at ",
          { text: "hello@edoardolunardi.dev", href: "mailto:hello@edoardolunardi.dev" },
          ".",
        ],
      ],
    },
  ],
};
