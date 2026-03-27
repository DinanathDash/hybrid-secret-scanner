import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";
const BACKEND_TIMEOUT_MS_FAST = Number(
  process.env.BACKEND_SCAN_TIMEOUT_MS_FAST ??
    process.env.BACKEND_SCAN_TIMEOUT_MS ??
    "120000",
);
const BACKEND_TIMEOUT_MS_LITE = Number(
  process.env.BACKEND_SCAN_TIMEOUT_MS_LITE ??
    process.env.BACKEND_SCAN_TIMEOUT_MS ??
    "300000",
);
const BACKEND_TIMEOUT_MS_FULL = Number(
  process.env.BACKEND_SCAN_TIMEOUT_MS_FULL ??
    process.env.BACKEND_SCAN_TIMEOUT_MS ??
    "600000",
);

export async function POST(request: Request) {
  let effectiveTimeoutMs = BACKEND_TIMEOUT_MS_FAST;
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return NextResponse.json(
      { error: "Invalid JSON body." },
      { status: 400 },
    );
  }

  try {
    const scanMode =
      typeof payload === "object" &&
      payload !== null &&
      "scan_mode" in payload &&
      typeof (payload as { scan_mode?: unknown }).scan_mode === "string"
        ? (payload as { scan_mode: string }).scan_mode.toLowerCase()
        : "fast";
    const normalizedMode: "fast" | "lite" | "full" =
      scanMode === "lite" || scanMode === "full" ? scanMode : "fast";

    effectiveTimeoutMs =
      normalizedMode === "full"
        ? BACKEND_TIMEOUT_MS_FULL
        : normalizedMode === "lite"
          ? BACKEND_TIMEOUT_MS_LITE
          : BACKEND_TIMEOUT_MS_FAST;

    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), effectiveTimeoutMs);
    let response: Response;
    try {
      response = await fetch(`${BACKEND_URL}/scan`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        cache: "no-store",
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }

    const data = (await response.json()) as unknown;
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    const isTimeout =
      error instanceof Error &&
      (error.name === "AbortError" || /aborted|timeout/i.test(error.message));
    const message =
      error instanceof Error ? error.message : "Unknown backend connection error.";
    return NextResponse.json(
      {
        error: isTimeout
          ? "Scanner backend timed out before responding."
          : "Unable to connect to scanner backend. Start backend/api_server.py and retry.",
        details: message,
        logs: isTimeout
          ? [
              `Proxy timeout after ${Math.round(effectiveTimeoutMs / 1000)}s.`,
              "If Full Scan is selected, model warm-up/download may be taking too long.",
              "Try Fast Scan first, or increase BACKEND_SCAN_TIMEOUT_MS.",
            ]
          : undefined,
      },
      { status: isTimeout ? 504 : 502 },
    );
  }
}
