#!/usr/bin/env python3
"""
Claude Code Approval Server
Läuft im Hintergrund, wartet auf Approval-Klicks via Email-Link
"""

import http.server
import socketserver
import json
import os
import time
import threading
from urllib.parse import urlparse, parse_qs
from pathlib import Path

APPROVAL_DIR = Path.home() / ".claude_approvals"
APPROVAL_DIR.mkdir(exist_ok=True)
PORT = 8742


class ApprovalHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/approve":
            token = params.get("token", [None])[0]
            action = params.get("action", ["unknown"])[0]

            if token:
                approval_file = APPROVAL_DIR / f"{token}.approved"
                approval_file.write_text("approved")

                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(self._approval_page(action).encode("utf-8"))
            else:
                self.send_response(400)
                self.end_headers()

        elif parsed.path == "/deny":
            token = params.get("token", [None])[0]
            action = params.get("action", ["unknown"])[0]

            if token:
                denial_file = APPROVAL_DIR / f"{token}.denied"
                denial_file.write_text("denied")

                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(self._denial_page(action).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Silent logging

    def _approval_page(self, action):
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Approved</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Courier New', monospace;
      background: #0a0a0a;
      color: #00ff88;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      border: 1px solid #00ff88;
      padding: 48px;
      max-width: 480px;
      text-align: center;
    }}
    .icon {{ font-size: 48px; margin-bottom: 24px; }}
    h1 {{ font-size: 24px; letter-spacing: 4px; margin-bottom: 16px; }}
    p {{ color: #888; font-size: 13px; line-height: 1.6; }}
    .action {{
      margin-top: 24px;
      padding: 12px;
      background: #00ff8811;
      border: 1px solid #00ff8833;
      font-size: 12px;
      color: #00ff88;
      word-break: break-all;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✓</div>
    <h1>APPROVED</h1>
    <p>Claude Code darf fortfahren.</p>
    <div class="action">{action}</div>
  </div>
</body>
</html>"""

    def _denial_page(self, action):
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Denied</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      font-family: 'Courier New', monospace;
      background: #0a0a0a;
      color: #ff4444;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
    }}
    .card {{
      border: 1px solid #ff4444;
      padding: 48px;
      max-width: 480px;
      text-align: center;
    }}
    .icon {{ font-size: 48px; margin-bottom: 24px; }}
    h1 {{ font-size: 24px; letter-spacing: 4px; margin-bottom: 16px; }}
    p {{ color: #888; font-size: 13px; line-height: 1.6; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✗</div>
    <h1>DENIED</h1>
    <p>Aktion wurde blockiert.</p>
  </div>
</body>
</html>"""


def wait_for_approval(token: str, timeout: int = 300) -> bool:
    """Wartet auf Approval oder Denial. Gibt True zurück wenn approved."""
    approved_file = APPROVAL_DIR / f"{token}.approved"
    denied_file = APPROVAL_DIR / f"{token}.denied"

    start = time.time()
    while time.time() - start < timeout:
        if approved_file.exists():
            approved_file.unlink()
            return True
        if denied_file.exists():
            denied_file.unlink()
            return False
        time.sleep(1)

    return False  # Timeout = deny


def start_server_background():
    """Startet den Server im Hintergrund."""
    with socketserver.TCPServer(("", PORT), ApprovalHandler) as httpd:
        httpd.serve_forever()


if __name__ == "__main__":
    print(f"[Claude Approval Server] läuft auf Port {PORT}")
    start_server_background()
