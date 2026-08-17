#!/usr/bin/env python3
"""webhook-listener.py — локальный mock-приёмник webhooks (ADR-009).

HTTP-сервер на 127.0.0.1:<port> (по умолчанию 8787). Каждый принятый POST JSON
пишет в outputs/07.007/webhooks/<epoch>.json и печатает событие в stdout.

Usage:
    python3 scripts/webhook-listener.py [port]
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ARCH = Path(__file__).resolve().parent.parent
WEBHOOKS_DIR = ARCH / "outputs" / "07.007" / "webhooks"


class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as e:
            payload = {"parse_error": str(e), "raw": raw.decode("utf-8", "replace")}

        WEBHOOKS_DIR.mkdir(parents=True, exist_ok=True)
        epoch = int(time.time() * 1000)
        out_path = WEBHOOKS_DIR / f"{epoch}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        event = payload.get("event", "?")
        tf = payload.get("tf_code", "")
        print(f"[WEBHOOK-RECV] {event} tf={tf} artifact={payload.get('artifact', '')} → {out_path.name}",
              flush=True)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))

    def log_message(self, format, *args):  # noqa: A002
        # тихий access-log
        pass


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
    server = HTTPServer(("127.0.0.1", port), WebhookHandler)
    print(f"[LISTENER] http://127.0.0.1:{port}/webhook — пишу в {WEBHOOKS_DIR}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[LISTENER] остановлен", flush=True)
        server.server_close()


if __name__ == "__main__":
    main()
