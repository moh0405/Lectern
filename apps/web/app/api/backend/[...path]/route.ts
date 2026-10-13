import { configFromEnv, forward } from "@/lib/backend-proxy";

// A cold API takes ~25 s to wake and an answer can take as long again.
export const maxDuration = 300;
export const dynamic = "force-dynamic";

async function handle(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  return forward(req, path, configFromEnv());
}

export { handle as GET, handle as POST, handle as PUT, handle as DELETE };
