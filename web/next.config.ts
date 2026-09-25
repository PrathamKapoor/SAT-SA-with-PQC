import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Do not generate AGENTS.md / CLAUDE.md into the project on dev start.
  agentRules: false,
  poweredByHeader: false,
  // Routes renamed in the prototype redesign.
  async redirects() {
    return [
      { source: "/workbench/trends", destination: "/workbench/analytics", permanent: true },
      { source: "/workbench/governance", destination: "/workbench/audit", permanent: true },
    ];
  },
};

export default nextConfig;
