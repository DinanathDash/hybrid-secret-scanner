import { NextResponse, type NextRequest } from "next/server";

/**
 * Intercepts Monaco Editor's loader.js.map request.
 * Monaco's AMD loader ships without its source map file, causing a browser
 * 404 on every page load. We return a valid empty source map to silence it.
 */
export function proxy(request: NextRequest) {
  return new NextResponse(
    JSON.stringify({ version: 3, sources: [], mappings: "" }),
    {
      status: 200,
      headers: { "Content-Type": "application/json; charset=utf-8" },
    },
  );
}

export const config = {
  matcher: "/:path*/loader.js.map",
};
