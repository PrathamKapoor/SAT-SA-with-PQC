import type { LearnMoreContent } from "../LearnMore";

const PORTRAIT = {
  src: "/sites/www-contentarchitecture-dev-80b3abaf/root-8a5edab2/avatars/maintainer.jpg",
  alt: "Man in black turtleneck smiling and looking to the side indoors",
};

/**
 * CA README drawer, verbatim from `dom/12-readme-drawer.html` (paragraphs generated from the live
 * DOM; split lines joined). The Mux video block in "Who am I" is not reproduced.
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
        ["Every Sanity project I shipped, the first week looked identical. Spin up Next, or Astro. Wire the Studio. Rewrite the page builder. Rebuild the SEO layer. Re-do the webhook revalidation. Re-style the same contact form for the fourth time."],
        ["By the time the actual creative work started, 3 days of the budget were gone and the client had not seen a single pixel that mattered."],
        ["Extracting it started small. One project. Then two. Then ten. Every time something broke in production, a Sanity migration that nuked a dataset, a CDN cache that served stale OG images for three weeks, a webhook that fired twice and corrupted a sitemap, the fix went back into the boilerplate."],
        ["For a long time I called this the cost of headless. I had rebuilt the same foundation so many times I could do it half-asleep, and I mistook that for being good at my job instead of what it was, doing the same work twice."],
        ["At some point that stopped being a reason to keep it to myself."],
        ["If you want the reasoning before you buy, I wrote it all down: ", { text: "CMS structure", href: "https://www.edoardolunardi.dev/blog/the-content-architecture-cms-structure" }, ", ", { text: "content models", href: "https://www.edoardolunardi.dev/blog/the-content-architecture-content-models" }, ", ", { text: "page composition", href: "https://www.edoardolunardi.dev/blog/the-content-architecture-page-composition" }, ", and ", { text: "content primitives", href: "https://www.edoardolunardi.dev/blog/the-content-architecture-content-primitives" }, ". The thinking behind every decision in the codebase, free to read."],
      ],
    },
    {
      id: "why-i-keep-shipping-it",
      number: "002",
      title: "Why I keep shipping it",
      paragraphs: [
        ["I use this on every project. I am the heaviest user. The bug I find on a Friday client engagement is the patch you get on Monday."],
        ["I am one person, not a team. That is a feature. The architecture is consistent because one mind held it from the first schema file to the last revalidation hook. Nobody overrode the opinion. Nobody added a field because a stakeholder asked nicely."],
        ["There is no distance between me and this. The decisions in the repo are the ones I make on paid work, in the same week, under the same deadline. When you open the fetch layer or the page builder, you are reading how I actually ship, not a demo cleaned up for sale. That is the whole relationship: you get the thing I rely on, maintained by the person who relies on it most."],
        ["I am not trying to turn this into a SaaS. There is no dashboard, no seat-based pricing, no telemetry. The roadmap is not fixed in stone either, it grows out of real client work: when a project turns up something worth having, it becomes part of the product. You buy the repo, you own the repo. I maintain it because I use it too."],
        ["Maintaining this in public is a forcing function for my own work. With paying users on both repos, I cannot let the schema rot, skip a Next.js or Astro major, or sit on a breaking change in a Sanity plugin. The same discipline is why an agent is useful on it: the calls are already made and written down, so it builds inside them instead of guessing. Your projects stay current because mine have to."],
      ],
    },
    {
      id: "who-am-i",
      number: "003",
      title: "Who am I",
      paragraphs: [
        ["I am Edo ", { image: PORTRAIT }, " - Creative Web Engineer, nearly a decade in. Sanity Pioneer 2026, Awwwards jury member, recognized across Awwwards, CSSDA, and FWA. I have shipped for Buck, Disney, Porsche, Red Bull, Le Labo Fragrances, Getty. Design sensibility, technical depth, obsessive about detail. Based in Vienna, working worldwide."],
        ["Find me on ", { text: "Instagram", href: "https://www.instagram.com/edo.tsx" }, ", ", { text: "LinkedIn", href: "https://www.linkedin.com/in/edoardolunardi" }, ", and ", { text: "X", href: "https://x.com/edo_lunardi" }, ". The work lives at ", { text: "edoardolunardi.dev", href: "https://www.edoardolunardi.dev/" }, ". Write to ", { text: "hello@edoardolunardi.dev", href: "mailto:hello@edoardolunardi.dev" }, "."],
      ],
    },
  ],
};
