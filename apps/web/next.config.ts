import type { NextConfig } from "next";

const config: NextConfig = {
  // The API client is shipped as TypeScript source.
  transpilePackages: ["@ai-study-mentor/api-client"],
  reactStrictMode: true,
};

export default config;
