import { NextResponse, type NextRequest } from "next/server";
import { legacyTutorTarget } from "@/lib/tutor-redirect";

// A route rather than a next.config redirect: those always pass the whole query through, `tool` included.
export function GET(request: NextRequest) {
  return NextResponse.redirect(new URL(legacyTutorTarget(request.nextUrl.searchParams), request.url), 307);
}
