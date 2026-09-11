import type {
  FaqItem,
  NumberedFeature,
  PricingEdition,
  ProblemRow,
  ShowcaseItem,
  Testimonial,
} from "@/types/content-architecture";

export const NAV_LINKS = [
  { label: "Features", href: "#features" },
  { label: "The repo", href: "#the-repo" },
  { label: "Showcase", href: "#showcase" },
  { label: "Pricing", href: "#pricing" },
  { label: "FAQ", href: "#faq" },
  { label: "Blog", href: "/blog" },
] as const;

export const STATUS_BADGES = [
  "NEXT 16.x",
  "ASTRO 7.x",
  "SANITY v6",
  "TS: STRICT",
  "AGENTS.MD: LOADED",
  "MCP: 2 SERVERS",
  "DRIFT: 0",
] as const;

export const PROBLEMS: ProblemRow[] = [
  { number: "001", title: "Agent redesigns the architecture on every prompt", time: "∞ HRS" },
  { number: "002", title: "Page builder schema + section registration + preview", time: "~5 HRS" },
  { number: "003", title: "Draft mode + live preview + webhook revalidation", time: "~4 HRS" },
  { number: "004", title: "CDN vs. data cache — stale content after publish", time: "~3 HRS" },
  { number: "005", title: "Studio structure editors can actually use", time: "~3 HRS" },
  { number: "006", title: "SEO metadata, OG images, sitemaps, robots.txt", time: "~2 HRS" },
  { number: "007", title: "Rewriting the same 12 components", time: "~2 HRS" },
  { number: "008", title: "Redirects, analytics, view transitions, Mux", time: "~1 HR" },
  { number: "009", title: "Contact form + spam guard + Resend wiring", time: "~1 HR" },
  { number: "010", title: "ESLint, Prettier, Biome, git hooks", time: "~1 HR" },
  { number: "011", title: "Basic auth for staging environments", time: "~1 HR" },
];

export const PROBLEMS_INTRO =
  "It's never the easy stuff that hurts. It's the page builder, modeled from scratch again. Draft mode and live preview, wired up and subtly broken again. The cache bug where published content goes stale and the client swears you shipped something wrong. A Studio structure your editors actually understand, instead of one they email you about. Then the parts that aren't even the CMS: metadata, redirects, spam-guarded forms, the staging password. This is the part nobody quotes for and everybody rebuilds. Days gone before the real work starts.";

export const FEATURES: NumberedFeature[] = [
  {
    number: "001",
    title: "Agent-native",
    description:
      "AGENTS.md and a dozen scoped skills load the conventions before the first prompt, so Claude Code or Cursor builds inside the decisions instead of proposing a new architecture per run. Two MCP servers ship in the repo: one reads the running app, one drives a real Chrome. The agent checks its own work.",
  },
  {
    number: "002",
    title: "Agent-ready in production",
    description:
      "The shipped site stays legible to agents: an editable llms.txt drafted from your content, and a token-light Markdown twin of every page on the same URL. A feature you can put in your own proposals.",
  },
  {
    number: "003",
    title: "Schema as a system",
    description:
      "Document roles, factory functions, singletons. Every schema looks the same, so every editor knows where to go. You never model the structure from scratch again.",
  },
  {
    number: "004",
    title: "The hard fields, already built",
    description:
      "The three fields nobody gets right the first time. A link field that handles every kind of link. A media field that returns image, Mux, Rive, and Lottie in one shape, dimensions included, so layout never shifts. A page builder with guardrails. Typed, composed everywhere.",
  },
  {
    number: "005",
    title: "Fetch layer, solved",
    description:
      "CDN bypassed in production, Data Cache doing the work, webhooks invalidating on publish, draft mode wired in. Stale content after publish stops being a midnight problem.",
  },
  {
    number: "006",
    title: "A Studio editors actually use",
    description:
      "Every document type where editors expect it. Pages own their routes, singletons stay locked, no hunting. Clients stop emailing to ask where their homepage lives.",
  },
  {
    number: "007",
    title: "SEO, done not deferred",
    description:
      "Per-page metadata from schema, sitemap driven by Sanity, OpenGraph with auto-cropped images, robots.txt included. Nothing bolted on the week before launch.",
  },
  {
    number: "008",
    title: "Production-ready from day one",
    description:
      "Basic auth, spam-protected forms, redirects managed in Sanity, analytics, view transitions. The plumbing you reconfigure every project, already wired.",
  },
  {
    number: "009",
    title: "Wired up, not just cloned",
    description:
      "An interactive setup script provisions the Sanity project, mints tokens, wires CORS and the revalidation webhook, and writes your .env. Migration scripts back up production and move content between environments. The first run is handled, not documented.",
  },
];

export const FEATURES_INTRO =
  "The production foundation under my client work: hundreds of decisions, schema, fetching, structure, SEO, deployment, made once over six years and committed. Clone it, rename it, ship. Committed decisions are also why agents work here: inside them an agent ships, without them it redesigns.";

export const REPO_TREE: string[] = [
  ".agents",
  ".zed",
  "app",
  "(web)",
  "api",
  "favicon.ico",
  "llms.txt",
  "openapi.json",
  "robots.txt",
  "sanity-studio",
  "global-not-found.tsx",
  "not-found.tsx",
  "shared-web-layout.tsx",
  "sitemap.ts",
  "components",
  "docs",
  "features",
  "agents",
  "auth",
  "blog",
  "dom",
  "draft-mode",
  "fonts",
  "forms",
  "legal",
  "motion",
  "mux",
  "page-builder",
  "rich-text",
  "sanity",
  "site",
  "spam-prevention",
  "style",
  "umami",
  "utils",
  "view-transition",
  "lenis.tsx",
  "use-content-ready.ts",
  "public",
  "scripts",
  "seed",
  "templates",
  ".env.example",
  ".gitignore",
  ".lefthookrc",
  ".mcp.json",
  ".npmrc",
  ".nvmrc",
  "AGENTS.md",
  "assets.d.ts",
  "biome.jsonc",
  "CLAUDE.md",
  "commitlint.config.mjs",
  "env.ts",
  "GETTING-STARTED.md",
  "lefthook.yml",
  "LICENSE.md",
  "next.config.ts",
  "package-lock.json",
  "package.json",
  "plopfile.mjs",
  "proxy.ts",
  "README.md",
  "GET-ACCESS.md",
  "sanity-schema.json",
  "sanity.cli.ts",
  "sanity.config.ts",
  "skills-lock.json",
  "tsconfig.json",
];

export const README_EXCERPT = {
  title: "The Content Architecture (Next.js)",
  intro:
    "A modern Next.js 16.3 starter with Sanity CMS integration: content model, in-app Studio, and product features, running on a Next.js App Router frontend.",
  features: [
    "Next.js 16.3 with the App Router and Server Components: the Studio and the API routes live on the same origin as the site",
    "Sanity CMS with the Studio mounted at /studio",
    "The pages model: a catch-all route renders any page document by its uri, homepage included",
    "Reusable page builder (text, media, CTA, contact form sections) rendered by self-fetching Server Components",
    "Rich text via Portable Text with media blocks, inline media, links, colors",
    "Media pipeline: Sanity images (responsive srcset + LQIP), Mux video, native video, Lottie, and Rive",
    "Draft mode with the Presentation tool, Sanity Live, and Visual Editing overlays",
    "SEO helpers: per-page metadata with Site singleton fallbacks, og:image cropping, per-scheme favicons, JSON-LD, CMS-driven sitemap and robots",
  ],
};

export const SHOWCASE_INTRO =
  "Real sites, shipped on The Content Architecture. With the plumbing already handled, the effort goes where it shows. The work here has been recognized by Awwwards, FWA, and CSSDA, and picked up across design directories.";

export const SHOWCASE_ITEMS: ShowcaseItem[] = [
  {
    name: "Good Fella",
    url: "https://good-fella.com/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-good-fella.jpg",
    alt: "Good Fella website built on The Content Architecture",
  },
  {
    name: "House of Honey",
    url: "https://www.houseofhoney.com/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-house-of-honey.jpg",
    alt: "House of Honey website built on The Content Architecture",
  },
  {
    name: "Aspen Search",
    url: "https://www.aspensearch.com/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-aspen-search.jpg",
    alt: "Aspen website hero section describing recruiting for software and AI/ML roles",
  },
  {
    name: "Anuc Home",
    url: "https://www.anuchome.com/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-anuc-home.jpg",
    alt: "Anuc Home website built on The Content Architecture",
  },
  {
    name: "Edoardo Lunardi",
    url: "https://www.edoardolunardi.dev/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-edoardo-lunardi.jpg",
    alt: "Portfolio website homepage for Edoardo Lunardi with featured article, about, and work gallery",
  },
  {
    name: "Serve Robotics",
    url: "https://www.serverobotics.com/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-serve-robotics.jpg",
    alt: "Serve Robotics website built on The Content Architecture",
  },
  {
    name: "Prism",
    url: "https://prismscience.org/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-prism.png",
    alt: "Prism website homepage with headline “Unlocking Protein Dynamics”",
  },
  {
    name: "Muralia",
    url: "https://www.muralia.at/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-muralia.jpg",
    alt: "Muralia website built on The Content Architecture",
  },
  {
    name: "blink",
    url: "https://www.blink.trade/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-blink.jpg",
    alt: "blink website built on The Content Architecture",
  },
  {
    name: "Creative Lives in Progress",
    url: "https://creativelivesinprogress.com/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-creative-lives.jpg",
    alt: "Creative Lives in Progress website built on The Content Architecture",
  },
  {
    name: "The Content Architecture",
    url: "https://www.contentarchitecture.dev/",
    image: "/sites/contentarchitecture-dev/root/images/showcase-content-architecture.png",
    alt: "Sanity landing page with headline “The Sanity setup agents don’t reinvent”",
  },
];

export const TESTIMONIALS: Testimonial[] = [
  {
    quote:
      "We shipped the Good Fella site on an early version and it saved us tons of time. Six months in, we're still building pages and sections in an afternoon without fighting the setup.",
    name: "Julian Fella",
    role: "Co-Founder, Good Fella",
    avatar: "/sites/contentarchitecture-dev/root/avatars/julian-fella.png",
  },
  {
    quote:
      "Edo and I ran a client project on this together. The plumbing was already handled, so the week we'd normally lose to setup went into the creative work the client actually remembers.",
    name: "Elliott Mangham",
    role: "Founder & Frontend Engineer",
    avatar: "/sites/contentarchitecture-dev/root/avatars/elliott-mangham.png",
  },
  {
    quote:
      "I opened the fetch layer and found the revalidation problem I'd burned two days on last project, already solved and committed. That one folder paid for the whole thing, and the rest is six years of decisions I'd have made the slow way.",
    name: "Malik Kotb",
    role: "Web Designer & Engineer",
    avatar: "/sites/contentarchitecture-dev/root/avatars/malik-kotb.png",
  },
];

export const PRICING_EDITIONS: PricingEdition[] = [
  {
    number: "001",
    eyebrow: "THE NEXT.JS 16 + SANITY V6 REPO",
    sub: "FOR NEXT.JS + SANITY ENGINEERS, NOT NO-CODE",
    price: "€399",
    oldPrice: "€549",
    ctaHref: "/checkout?plan=next",
  },
  {
    number: "002",
    eyebrow: "THE ASTRO 7 + SANITY V6 REPO",
    sub: "FOR ASTRO + SANITY ENGINEERS, NOT NO-CODE",
    price: "€399",
    oldPrice: "€549",
    ctaHref: "/checkout?plan=astro",
  },
];

export const PRICING_INCLUDES: string[] = [
  "ONE-TIME FEE, NO SUBSCRIPTION",
  "PERPETUAL LICENSE, UNLIMITED PROJECTS",
  "COMMERCIAL USE, NO ATTRIBUTION",
  "LIFETIME UPDATES, INCLUDED",
  "AGENT-READY: SKILLS, MCP, LLMS.TXT",
  "PRIVATE GITHUB DISCUSSIONS",
  "DIRECT LINE TO THE MAINTAINER",
  "FULL SOURCE ON PURCHASE, SALES FINAL",
  "ALL PRICES IN EUR",
];

export const FAQ_ITEMS: FaqItem[] = [
  {
    number: "001",
    question: "What stack is this built on?",
    answer:
      "Two editions, one architecture. The Next.js edition runs Next.js 16 with the App Router and React Compiler; the Astro edition runs Astro 7. Both share Sanity v6, TypeScript in strict mode, Tailwind 4, and Biome for lint and format. Deploys on Vercel out of the box; the Next.js edition also runs on Cloudflare via OpenNext.",
  },
  {
    number: "002",
    question: "Does it work with Claude Code and Cursor?",
    answer:
      "It is built for it. AGENTS.md plus a dozen scoped skills mean any agentic tool ingests the conventions and boundaries before you write a prompt. Ask an agent to build this from scratch and you get a different architecture every run. Here the decisions are already made, so the agent works inside them instead of inventing new ones. It also ships two preconfigured MCP servers: one reads the running Next.js dev server, the other drives a real Chrome.",
  },
  {
    number: "003",
    question: "Is the shipped site agent-ready too?",
    answer:
      "Yes. Every site built on this ships with an editable llms.txt, drafted from your content with Sanity Agent Actions from the Site document, and a token-light Markdown version of every page and article, served on the same URL to any agent that sends Accept: text/markdown.",
  },
  {
    number: "004",
    question: "Am I locked into this exact stack?",
    answer:
      "No. The opinion lives in the architecture, and the tools sit on top of it. Tailwind, Biome, Mux, Rive, Lottie, these are the defaults I reach for on most projects, wired in cleanly so they come out just as cleanly. The Sanity layer is decoupled by design too: every import inside the sanity/ folder is relative or an external package.",
  },
  {
    number: "005",
    question: "Can I buy both editions?",
    answer:
      "Yes, and you should not pay twice for the same architecture. Both editions model content the same way, so the second repo is mostly a re-read of patterns you already know. Email me from the address you bought with and I will send you a discount code for the second edition.",
  },
  {
    number: "006",
    question: "Do I need to know Sanity?",
    answer:
      "Some, yes. This is a real codebase, not a no-code template. You should be comfortable in a Sanity schema file and a Next.js or Astro project. If you have never opened a schema, the article series is the best place to start before deciding.",
  },
  {
    number: "007",
    question: "Is this for me if I don't code?",
    answer:
      "No, and I'd rather tell you here than take your money. This is a real Next.js or Astro and Sanity codebase, not a no-code tool: no visual page builder, no drag-and-drop editor.",
  },
  {
    number: "008",
    question: "Can I use this for client work?",
    answer:
      "Yes. Unlimited projects, commercial use, no attribution required. Use it on every client site you ship. The one thing you cannot do is resell the architecture itself as a competing product.",
  },
  {
    number: "009",
    question: "How is this different from other boilerplates?",
    answer:
      "Most boilerplates give you a pile of features. This gives you decisions. Every hard call, document modeling, the fetch layer, revalidation, the link and media fields, was made once over six years and committed.",
  },
  {
    number: "010",
    question: "Why not just use a free Sanity starter?",
    answer:
      "A free starter gets you a clean install and the easy parts. What it leaves you is the work that actually costs the days: a page builder with guardrails, the fetch layer and revalidation, the link and media fields, a Studio structure your editors don't email you about.",
  },
  {
    number: "011",
    question: "Will it break on Next.js or Astro updates?",
    answer:
      "This is my daily driver, so I keep it current. Next.js and Astro majors, Sanity migrations, breaking plugin changes, I handle them and push the update. Your license includes every update for as long as I maintain it.",
  },
  {
    number: "012",
    question: "What do I actually get, and for how long?",
    answer:
      "The full repo on day one, a perpetual license, and lifetime updates included, not sold as a separate tier. One payment, no subscription. You own it forever.",
  },
  {
    number: "013",
    question: "Do I need a GitHub account?",
    answer:
      "Yes. The repo is delivered as private GitHub access: you enter your username at checkout, and access is granted to that exact account, including every future update.",
  },
  {
    number: "014",
    question: "Do you offer support?",
    answer:
      "Buyers get a private GitHub Discussions space, threaded and searchable, where I answer questions directly. For anything bigger, I am reachable by email.",
  },
  {
    number: "015",
    question: "What if I find a bug?",
    answer:
      "Tell me, and it gets fixed in the codebase, usually fast. A bug you hit is a bug my own client projects will hit too, so fixing it is in my interest as much as yours. The patch ships to everyone.",
  },
  {
    number: "016",
    question: "Can I get a refund?",
    answer:
      "Because you get the full source on purchase, sales are final, the same way every serious code product works. Once the repo is cloned, it cannot be un-cloned. If something is unclear before you buy, email me and I will answer honestly.",
  },
  {
    number: "017",
    question: "What is this not?",
    answer:
      "It is a set of architectural decisions, made once over six years and committed, that gets you to the real work faster. You write real code on top of it. There is no no-code editor, no UI kit or component library to theme, no auth-billing-dashboard SaaS scaffolding.",
  },
];

export const FOOTER_LINKS = {
  primary: [
    { label: "Blog", href: "/blog" },
    { label: "Roadmap", href: "/roadmap" },
    { label: "Get access", href: "#pricing" },
  ],
  legal: [
    { label: "Privacy Policy", href: "/legal/privacy-policy" },
    { label: "Terms Of Service", href: "/legal/terms-of-service" },
    { label: "Imprint", href: "/legal/imprint" },
  ],
} as const;

export const AWARDS = [
  { label: "Awwwards", href: "https://www.awwwards.com/" },
  { label: "FWA", href: "https://thefwa.com/" },
  { label: "CSSDA", href: "https://www.cssdesignawards.com/" },
] as const;
