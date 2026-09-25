import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // Do not generate AGENTS.md / CLAUDE.md into the project on dev start.
  agentRules: false,
  poweredByHeader: false,
};

export default nextConfig;
