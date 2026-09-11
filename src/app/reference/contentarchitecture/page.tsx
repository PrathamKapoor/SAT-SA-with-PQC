import type { Metadata } from "next";
import { PageShell } from "@/components/sites/www-contentarchitecture-dev-80b3abaf/shared/PageShell";

export const metadata: Metadata = {
  title: "Agent-Ready Sanity Kit for Next.js & Astro | The Content Architecture",
  description:
    "The agent-ready Sanity kit for Next.js and Astro. Six years of decisions committed: page builder, fetch layer, AGENTS.md, skills, MCP servers, llms.txt. Buy once, own it forever.",
  robots: { index: false, follow: false },
  icons: {
    icon: [
      { url: "/sites/www-contentarchitecture-dev-80b3abaf/shared/seo/icon-light.png", media: "(prefers-color-scheme: light)" },
      { url: "/sites/www-contentarchitecture-dev-80b3abaf/shared/seo/icon-dark.png", media: "(prefers-color-scheme: dark)" },
    ],
  },
};

export default function ContentArchitectureReferencePage() {
  return (
    <PageShell>
      <div className="bg-off-white" />
    </PageShell>
  );
}
