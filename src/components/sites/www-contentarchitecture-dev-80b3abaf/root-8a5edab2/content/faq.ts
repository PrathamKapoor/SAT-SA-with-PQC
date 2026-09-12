import { decodeGlyphFieldModel } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/glyph-model";
import glyphPhrases from "../data/glyph-phrases.json";
import orbModel from "../data/orb-model.json";
import type { FaqContent } from "../FaqSection";

const ARTICLE_SERIES_URL = "https://www.edoardolunardi.dev/blog/the-content-architecture-cms-structure";
const EMAIL_HREF = "mailto:hello@edoardolunardi.dev";

export const faqContent: FaqContent = {
  id: "faq",
  title: "Before you buy",
  cta: { leftText: "Get", rightText: "access", href: "#pricing" },
  items: [
    {
      question: "What stack is this built on?",
      answer: [
        "Two editions, one architecture. The Next.js edition runs Next.js 16 with the App Router and React Compiler; the Astro edition runs Astro 7. Both share Sanity v6, TypeScript in strict mode, Tailwind 4, and Biome for lint and format. Deploys on Vercel out of the box; the Next.js edition also runs on Cloudflare via OpenNext.",
      ],
    },
    {
      question: "Does it work with Claude Code and Cursor?",
      answer: [
        "It is built for it. AGENTS.md plus a dozen scoped skills mean any agentic tool ingests the conventions and boundaries before you write a prompt. Ask an agent to build this from scratch and you get a different architecture every run. Here the decisions are already made, so the agent works inside them instead of inventing new ones. You still read and write the real code yourself; the agent works inside the architecture, it does not write the app for you.",
        "It also ships two preconfigured MCP servers. One reads the running Next.js dev server: compilation errors, routes, docs that match the installed version. The other drives a real Chrome: screenshots across viewports, performance traces, screencasts of transitions it can review frame by frame. The agent doesn't just know the conventions, it can look at the app it's changing.",
      ],
    },
    {
      question: "Is the shipped site agent-ready too?",
      answer: [
        "Yes. Every site built on this ships with an editable llms.txt, drafted from your content with Sanity Agent Actions from the Site document, and a token-light Markdown version of every page and article, served on the same URL to any agent that sends Accept: text/markdown. You generate it per page in Studio, review it, and it is served verbatim. Your client's site is readable by assistants and agentic crawlers on day one, a line item you can put in your own proposal.",
      ],
    },
    {
      question: "Am I locked into this exact stack?",
      answer: [
        "No. The opinion lives in the architecture, and the tools sit on top of it. Tailwind, Biome, Mux, Rive, Lottie, these are the defaults I reach for on most projects, wired in cleanly so they come out just as cleanly. Don't want Tailwind? Pull it. Prefer ESLint over Biome? Swap it. No Mux, Rive, or Lottie in this project? Drop them. What you are really buying is the patterns underneath, how content is modeled, fetched, and composed. The libraries are just what I ship with on 90% of my projects.",
        "The Sanity layer is decoupled by design too. Every import inside the sanity/ folder is relative or an external package, nothing reaches into the app code, so you can lift the whole Studio, schema, and field primitives into another project. The content layer doesn't hold you hostage to the front end.",
      ],
    },
    {
      question: "Can I buy both editions?",
      answer: [
        "Yes, and you should not pay twice for the same architecture. Both editions model content the same way, so the second repo is mostly a re-read of patterns you already know. If you own one and want the other, whether that is today or a year from now, you pay a reduced price for it.",
        [
          "There is no automatic checkout for it. ",
          { text: "Email me", href: EMAIL_HREF },
          " from the address you bought with and I will send you a discount code for the second edition.",
        ],
      ],
    },
    {
      question: "Do I need to know Sanity?",
      answer: [
        "Some, yes. This is a real codebase, not a no-code template. You should be comfortable in a Sanity schema file and a Next.js or Astro project. If you are, you will feel at home in minutes. If you have never opened a schema, the article series is the best place to start before deciding.",
      ],
    },
    {
      question: "Is this for me if I don't code?",
      answer: [
        "No, and I'd rather tell you here than take your money. This is a real Next.js or Astro and Sanity codebase, not a no-code tool: no visual page builder, no drag-and-drop editor. You clone the repo and write real code on top of it. If you don't work in Next.js or Astro with Sanity, it isn't for you.",
      ],
    },
    {
      question: "Can I use this for client work?",
      answer: [
        "Yes. Unlimited projects, commercial use, no attribution required. Use it on every client site you ship. The one thing you cannot do is resell the architecture itself as a competing product.",
      ],
    },
    {
      question: "How is this different from other boilerplates?",
      answer: [
        "Most boilerplates give you a pile of features. This gives you decisions. Every hard call, document modeling, the fetch layer, revalidation, the link and media fields, was made once over six years and committed. It is opinionated on purpose, and it is the architecture I ship my own client work on, not a side project cleaned up for sale.",
      ],
    },
    {
      question: "Why not just use a free Sanity starter?",
      answer: [
        "A free starter gets you a clean install and the easy parts. What it leaves you is the work that actually costs the days: a page builder with guardrails, the fetch layer and revalidation, the link and media fields, a Studio structure your editors don't email you about. Those decisions are still yours to make on every project. Here they're already made, over six years of real client work, and committed. You're not paying for code you could scaffold in an afternoon. You're paying to skip the part nobody quotes for.",
      ],
    },
    {
      question: "Will it break on Next.js or Astro updates?",
      answer: [
        "This is my daily driver, so I keep it current. Next.js and Astro majors, Sanity migrations, breaking plugin changes, I handle them and push the update. Your license includes every update for as long as I maintain it, which is for as long as I am using it myself.",
      ],
    },
    {
      question: "What do I actually get, and for how long?",
      answer: [
        "The full repo on day one, a perpetual license, and lifetime updates included, not sold as a separate tier. One payment, no subscription. You own it forever.",
      ],
    },
    {
      question: "Do I need a GitHub account?",
      answer: [
        [
          "Yes. The repo is delivered as private GitHub access: you enter your username at checkout, and access is granted to that exact account, including every future update. No account yet? ",
          { text: "Creating one", href: "https://github.com/signup", external: true },
          " takes a minute, then come back and buy.",
        ],
      ],
    },
    {
      question: "Do you offer support?",
      answer: [
        "Buyers get a private GitHub Discussions space, threaded and searchable, where I answer questions directly. For anything bigger, I am reachable by email. What you will not find is a Discord to get lost in or a support queue that routes you to a bot.",
      ],
    },
    {
      question: "What if I find a bug?",
      answer: [
        "Tell me, and it gets fixed in the codebase, usually fast. A bug you hit is a bug my own client projects will hit too, so fixing it is in my interest as much as yours. The patch ships to everyone.",
      ],
    },
    {
      question: "Can I get a refund?",
      answer: [
        [
          "Because you get the full source on purchase, sales are final, the same way every serious code product works. Once the repo is cloned, it cannot be un-cloned. So I have put everything you need to decide up front: ",
          { text: "read the article series", href: ARTICLE_SERIES_URL, external: true },
          " for the full reasoning, ",
          { text: "browse the real repo above", href: "/#the-repo" },
          ", and look at the ",
          { text: "sites already shipped", href: "/#showcase" },
          " on it. If something is unclear before you buy, ",
          { text: "email me", href: EMAIL_HREF },
          " and I will answer honestly, sometimes that means telling you it is not the right fit.",
        ],
      ],
    },
    {
      question: "What is this not?",
      answer: [
        [
          "It is a set of architectural decisions, made once over six years and committed, that gets you to the real work faster. You write real code on top of it. There is no no-code editor, no UI kit or component library to theme, no auth-billing-dashboard SaaS scaffolding, and no course wrapped around it, though the ",
          { text: "article series", href: ARTICLE_SERIES_URL, external: true },
          " explains the reasoning behind it. You buy it once and own it.",
        ],
      ],
    },
  ],
  glyph: {
    model: decodeGlyphFieldModel(orbModel),
    phrase: glyphPhrases.phrases.faq,
  },
};
