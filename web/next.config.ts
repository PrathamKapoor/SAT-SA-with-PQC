import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Do not generate AGENTS.md / CLAUDE.md into the project on dev start.
  agentRules: false,
  poweredByHeader: false,
  experimental: {
    // Evidence files pass through a server action on their way to the SAT-SA API,
    // which accepts request bodies up to SATSA_MAX_REQUEST_BYTES (default 17 MiB).
    serverActions: { bodySizeLimit: "17mb" },
  },
  // Routes renamed in the prototype redesign.
  async redirects() {
    return [
      { source: "/workbench/trends", destination: "/workbench/analytics", permanent: true },
      { source: "/workbench/governance", destination: "/workbench/audit", permanent: true },
      { source: "/workbench/overview", destination: "/workbench", permanent: false },
      { source: "/workbench/pipeline", destination: "/workbench/runs", permanent: false },
    ];
  },
};

export default nextConfig;
