import type { NextConfig } from "next";

const config: NextConfig = {
  // The API client is shipped as TypeScript source.
  transpilePackages: ["@ai-study-mentor/api-client"],
  reactStrictMode: true,
  // Headless local previews use the loopback IP; keep dev resources local-only.
  allowedDevOrigins: ["127.0.0.1"],
};

export default config;
