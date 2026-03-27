from __future__ import annotations

import argparse
import asyncio
import json
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from src.llm_engine import (
    CONFIRMED_SECRET_PRIORITIES,
    get_cache_stats,
    get_llm_runtime_status,
    get_warmup_status,
    warmup_llm_if_configured,
)
from src.scanner import FullScanError, scan_snippet


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hybrid Secret Scanner API server")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    return parser.parse_args()


class ScannerRequestHandler(BaseHTTPRequestHandler):
    server_version = "HybridSecretScanner/1.0"

    def _send_json(self, status: HTTPStatus, payload: dict) -> bool:
        body = json.dumps(payload).encode("utf-8")
        try:
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)
            return True
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected before receiving the response.
            return False

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT.value)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            warmup_done, warmup_message = get_warmup_status()
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "warmup_done": warmup_done,
                    "warmup_message": warmup_message,
                },
            )
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/scan":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length)

        try:
            payload = json.loads(raw_body or b"{}")
            code = payload.get("code", "")
            filename = payload.get("filename", "snippet.txt")
            scan_mode = payload.get("scan_mode", "fast")
            if (
                not isinstance(code, str)
                or not isinstance(filename, str)
                or not isinstance(scan_mode, str)
            ):
                raise ValueError("`code`, `filename`, and `scan_mode` must be strings.")
            scan_mode = scan_mode.lower().strip()
            if scan_mode not in {"fast", "lite", "full"}:
                raise ValueError("`scan_mode` must be one of 'fast', 'lite', or 'full'.")
        except Exception as exc:
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": f"Invalid request payload: {exc}"},
            )
            return

        try:
            started_at = time.perf_counter()
            findings, effective_mode = asyncio.run(
                scan_snippet(code=code, filename=filename, scan_mode=scan_mode)
            )
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            duration_seconds = round(duration_ms / 1000, 3)
            api_findings = []
            for candidate, verdict in findings:
                api_findings.append(
                    {
                        "line_number": candidate.line_number,
                        "secret_category": candidate.secret_category,
                        "is_genuine_secret": verdict.is_genuine_secret,
                        "confidence_score": verdict.confidence_score,
                        "confidence_method": (
                            "heuristic_entropy_band"
                            if effective_mode == "fast"
                            else ("llm_lite_score" if effective_mode == "lite" else "llm_reported_score")
                        ),
                        "remediation_priority": verdict.remediation_priority,
                        "reasoning": verdict.reasoning,
                    }
                )

            confirmed_count = sum(
                1
                for item in api_findings
                if item["remediation_priority"] in CONFIRMED_SECRET_PRIORITIES
            )
            llm_runtime_ready, llm_runtime_reason = get_llm_runtime_status()
            warmup_done, warmup_message = get_warmup_status()
            cache_stats = get_cache_stats()
            logs = [
                f"Request accepted. mode={scan_mode}, filename={filename}",
                f"Candidate extraction complete. total_candidates={len(api_findings)}",
                f"Classification complete. confirmed_count={confirmed_count}",
                f"Effective mode={effective_mode}",
                f"Duration={duration_seconds}s",
                f"LLM runtime ready={llm_runtime_ready}. reason={llm_runtime_reason}",
                f"Model warmup done={warmup_done}. message={warmup_message}",
                (
                    "LLM cache "
                    f"enabled={cache_stats['enabled']} size={cache_stats['size']} "
                    f"hits={cache_stats['hits']} misses={cache_stats['misses']}"
                ),
            ]

            self._send_json(
                HTTPStatus.OK,
                {
                    "scan_mode_requested": scan_mode,
                    "scan_mode_effective": effective_mode,
                    "duration_ms": duration_ms,
                    "duration_seconds": duration_seconds,
                    "llm_runtime": {
                        "ready": llm_runtime_ready,
                        "reason": llm_runtime_reason,
                    },
                    "status": "threat" if confirmed_count > 0 else "clean",
                    "summary": {
                        "total_candidates": len(api_findings),
                        "confirmed_count": confirmed_count,
                    },
                    "findings": api_findings,
                    "logs": logs,
                },
            )
        except FullScanError as exc:
            llm_runtime_ready, llm_runtime_reason = get_llm_runtime_status()
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": str(exc),
                    "scan_mode_requested": scan_mode,
                    "scan_mode_effective": scan_mode,
                    "llm_runtime": {
                        "ready": llm_runtime_ready,
                        "reason": llm_runtime_reason,
                    },
                    "logs": ["Full scan error encountered.", *exc.logs],
                },
            )
        except Exception as exc:
            try:
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"error": f"Scan failed: {exc}", "logs": [f"Unhandled error: {exc}"]},
                )
            except Exception:
                # Avoid noisy traceback loops when client is already disconnected.
                pass

    def log_message(self, fmt: str, *args: object) -> None:
        # Keep API output concise during local development.
        print(f"[api] {self.address_string()} - {fmt % args}")


def main() -> None:
    args = _parse_args()
    warmed, warm_msg = warmup_llm_if_configured()
    httpd = ThreadingHTTPServer((args.host, args.port), ScannerRequestHandler)
    print(f"Starting API server on http://{args.host}:{args.port}")
    print("Endpoints: GET /health, POST /scan")
    print(f"Model warmup: {'ready' if warmed else 'not ready'} ({warm_msg})")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down API server.")
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
