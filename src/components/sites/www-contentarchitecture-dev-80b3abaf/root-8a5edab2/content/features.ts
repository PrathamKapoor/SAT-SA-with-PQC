import type { FeaturesContent } from "../FeaturesSection";
import { decodeGlyphFieldModel } from "../../shared/glyph-model";
import orbModel from "../data/orb-model.json";
import glyphPhrases from "../data/glyph-phrases.json";

export const featuresContent: FeaturesContent = {
  id: "features",
  title: "Every decision already made.\nSo you can skip to the actual work.",
  intro: [
    "The production foundation under my client work: hundreds of decisions, schema, fetching, structure, SEO, deployment, made once over six years and committed. Clone it, rename it, ship. Committed decisions are also why agents work here: inside them an agent ships, without them it redesigns.",
  ],
  items: [
    {
      num: "001",
      title: "Agent-native",
      body: "AGENTS.md and a dozen scoped skills load the conventions before the first prompt, so Claude Code or Cursor builds inside the decisions instead of proposing a new architecture per run. Two MCP servers ship in the repo: one reads the running app, one drives a real Chrome. The agent checks its own work.",
    },
    {
      num: "002",
      title: "Agent-ready in production",
      body: "The shipped site stays legible to agents: an editable llms.txt drafted from your content, and a token-light Markdown twin of every page on the same URL. A feature you can put in your own proposals.",
    },
    {
      num: "003",
      title: "Schema as a system",
      body: "Document roles, factory functions, singletons. Every schema looks the same, so every editor knows where to go. You never model the structure from scratch again.",
    },
    {
      num: "004",
      title: "The hard fields, already built",
      body: "The three fields nobody gets right the first time. A link field that handles every kind of link. A media field that returns image, Mux, Rive, and Lottie in one shape, dimensions included, so layout never shifts. A page builder with guardrails. Typed, composed everywhere.",
    },
    {
      num: "005",
      title: "Fetch layer, solved",
      body: "CDN bypassed in production, Data Cache doing the work, webhooks invalidating on publish, draft mode wired in. Stale content after publish stops being a midnight problem.",
    },
    {
      num: "006",
      title: "A Studio editors actually use",
      body: "Every document type where editors expect it. Pages own their routes, singletons stay locked, no hunting. Clients stop emailing to ask where their homepage lives.",
    },
    {
      num: "007",
      title: "SEO, done not deferred",
      body: "Per-page metadata from schema, sitemap driven by Sanity, OpenGraph with auto-cropped images, robots.txt included. Nothing bolted on the week before launch.",
    },
    {
      num: "008",
      title: "Production-ready from day one",
      body: "Basic auth, spam-protected forms, redirects managed in Sanity, analytics, view transitions. The plumbing you reconfigure every project, already wired.",
    },
    {
      num: "009",
      title: "Wired up, not just cloned",
      body: "An interactive setup script provisions the Sanity project, mints tokens, wires CORS and the revalidation webhook, and writes your .env. Migration scripts back up production and move content between environments. The first run is handled, not documented.",
    },
  ],
  glyph: {
    model: decodeGlyphFieldModel(orbModel),
    phrase: glyphPhrases.phrases.features,
  },
};
