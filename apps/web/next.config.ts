import type { NextConfig } from "next";

const config: NextConfig = {
  // The API client is shipped as TypeScript source.
  transpilePackages: ["@ai-study-mentor/api-client"],
  reactStrictMode: true,
  // Headless local previews use the loopback IP; keep dev resources local-only.
  allowedDevOrigins: ["127.0.0.1"],
  // The four tutor tools used to be tabs on /tutor (`?tool=`); each now has its own page. Old links and
  // bookmarks keep working. Other query parameters (for example `topic`) are passed through.
  async redirects() {
    const tool = (value: string, destination: string) => ({
      source: "/tutor",
      has: [{ type: "query" as const, key: "tool", value }],
      destination,
      permanent: false,
    });
    return [
      tool("map", "/concept-map"),
      tool("socratic", "/work-it-out"),
      tool("synthesis", "/compare"),
      tool("adaptive", "/explain"),
      { source: "/tutor", destination: "/concept-map", permanent: false },
    ];
  },
};

export default config;
