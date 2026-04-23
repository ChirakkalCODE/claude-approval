#!/usr/bin/env python3
"""
Claude Code Pre-Tool Hook
Fängt kritische Befehle ab, sendet Gmail-Bestätigung, wartet auf Klick.

Setup:
  Umgebungsvariablen setzen (einmalig in ~/.bashrc oder ~/.zshrc):
    APPROVAL_EMAIL_FROM=deine@gmail.com
    APPROVAL_EMAIL_PASSWORD=dein-app-passwort   # Gmail App-Passwort, nicht normales PW
    APPROVAL_EMAIL_TO=deine@gmail.com           # wohin die Email geht (kann gleich sein)
    APPROVAL_BASE_URL=http://localhost:8742     # oder ngrok URL für unterwegs
"""

import sys
import json
import os
import smtplib
import secrets
import subprocess
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# ─── Konfiguration ────────────────────────────────────────────────────────────

EMAIL_FROM     = os.environ.get("APPROVAL_EMAIL_FROM", "")
EMAIL_PASSWORD = os.environ.get("APPROVAL_EMAIL_PASSWORD", "")
EMAIL_TO       = os.environ.get("APPROVAL_EMAIL_TO", EMAIL_FROM)
BASE_URL       = os.environ.get("APPROVAL_BASE_URL", "http://localhost:8742")
TIMEOUT        = int(os.environ.get("APPROVAL_TIMEOUT", "300"))  # 5 Minuten

# ─── Kritische Muster ─────────────────────────────────────────────────────────

CRITICAL_PATTERNS = [
    # Git
    "git push",
    "git push --force",
    "git push -f",
    # Dateien löschen
    "rm ",
    "rm -rf",
    "del ",
    "rmdir",
    "Remove-Item",
    # Packages installieren
    "pip install",
    "npm install",
    "npm i ",
    "yarn add",
    "pip uninstall",
    "npm uninstall",
    "choco install",
    "winget install",
    # Gefährliche System-Befehle
    "format ",
    "mkfs",
    "dd if=",
    "shutdown",
    "reboot",
    # Credentials / Secrets
    "export ",
    "set ",
]

# Diese Patterns sind immer OK (Whitelist)
SAFE_PATTERNS = [
    "git status",
    "git log",
    "git diff",
    "git branch",
    "ls ",
    "dir ",
    "cat ",
    "echo ",
    "python --version",
    "node --version",
    "pip show",
    "pip list",
    "npm list",
]


def is_critical(command: str) -> bool:
    """Prüft ob ein Befehl kritisch ist."""
    cmd_lower = command.lower().strip()

    # Whitelist zuerst prüfen
    for safe in SAFE_PATTERNS:
        if cmd_lower.startswith(safe.lower()):
            return False

    # Kritische Patterns prüfen
    for pattern in CRITICAL_PATTERNS:
        if pattern.lower() in cmd_lower:
            return True

    return False


def send_approval_email(token: str, command: str, tool_name: str) -> bool:
    """Sendet eine Gmail mit Approve/Deny Links."""
    if not EMAIL_FROM or not EMAIL_PASSWORD:
        print("[Hook] APPROVAL_EMAIL_FROM oder APPROVAL_EMAIL_PASSWORD nicht gesetzt", file=sys.stderr)
        print("[Hook] Befehl wird BLOCKIERT (keine Email-Konfiguration)", file=sys.stderr)
        return False

    approve_url = f"{BASE_URL}/approve?token={token}&action={command[:100]}"
    deny_url    = f"{BASE_URL}/deny?token={token}&action={command[:100]}"

    html = f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ font-family: -apple-system, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
    .container {{ max-width: 560px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }}
    .header {{ background: #1a1a1a; color: white; padding: 24px; }}
    .header h1 {{ margin: 0; font-size: 18px; letter-spacing: 1px; }}
    .header p {{ margin: 4px 0 0; color: #888; font-size: 13px; }}
    .body {{ padding: 24px; }}
    .command {{ background: #f8f8f8; border-left: 3px solid #ff6b35; padding: 12px 16px; font-family: monospace; font-size: 14px; margin: 16px 0; word-break: break-all; border-radius: 0 4px 4px 0; }}
    .label {{ font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #999; margin-bottom: 4px; }}
    .buttons {{ display: flex; gap: 12px; margin-top: 24px; }}
    .btn {{ flex: 1; padding: 14px; text-align: center; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px; }}
    .btn-approve {{ background: #00c853; color: white; }}
    .btn-deny {{ background: #ff1744; color: white; }}
    .footer {{ padding: 16px 24px; background: #f8f8f8; font-size: 12px; color: #999; border-top: 1px solid #eee; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>⚡ Claude Code — Bestätigung erforderlich</h1>
      <p>Eine kritische Aktion wartet auf deine Freigabe</p>
    </div>
    <div class="body">
      <div class="label">Tool</div>
      <strong>{tool_name}</strong>

      <div class="label" style="margin-top:16px">Befehl</div>
      <div class="command">{command}</div>

      <div class="buttons">
        <a href="{approve_url}" class="btn btn-approve">✓ Approve</a>
        <a href="{deny_url}" class="btn btn-deny">✗ Deny</a>
      </div>
    </div>
    <div class="footer">
      Diese Anfrage läuft in {TIMEOUT // 60} Minuten ab. Bei keiner Antwort wird die Aktion blockiert.
    </div>
  </div>
</body>
</html>
"""

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"⚡ Claude Code: Bestätigung für '{command[:50]}'"
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(EMAIL_FROM, EMAIL_TO, msg.as_string())

        return True
    except Exception as e:
        print(f"[Hook] Email-Fehler: {e}", file=sys.stderr)
        return False


def ensure_server_running():
    """Startet den Approval-Server falls er nicht läuft."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        result = s.connect_ex(("localhost", 8742))
        s.close()
        if result == 0:
            return  # Server läuft bereits
    except:
        pass

    # Server starten
    script_dir = Path(__file__).parent
    server_script = script_dir / "approval_server.py"
    subprocess.Popen(
        [sys.executable, str(server_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    )
    time.sleep(1)  # Server hochfahren lassen


def wait_for_approval(token: str) -> bool:
    """Wartet auf Approval vom Server."""
    approval_dir = Path.home() / ".claude_approvals"
    approval_dir.mkdir(exist_ok=True)

    approved_file = approval_dir / f"{token}.approved"
    denied_file   = approval_dir / f"{token}.denied"

    start = time.time()
    while time.time() - start < TIMEOUT:
        if approved_file.exists():
            approved_file.unlink()
            return True
        if denied_file.exists():
            denied_file.unlink()
            return False
        time.sleep(1)

    return False  # Timeout


def main():
    # Claude Code übergibt Tool-Input als JSON via stdin
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except:
        data = {}

    tool_name = data.get("tool_name", "unknown")
    tool_input = data.get("tool_input", {})

    # Befehl aus dem Input extrahieren
    command = ""
    if isinstance(tool_input, dict):
        command = (
            tool_input.get("command", "") or
            tool_input.get("cmd", "") or
            tool_input.get("input", "") or
            str(tool_input)
        )
    else:
        command = str(tool_input)

    # Nicht-kritische Befehle durchlassen
    if not is_critical(command):
        sys.exit(0)  # 0 = Claude Code darf weitermachen

    # ─── Kritischer Befehl erkannt ────────────────────────────────────────────
    print(f"\n[🔒 Approval Required] Kritische Aktion erkannt:", file=sys.stderr)
    print(f"   Tool: {tool_name}", file=sys.stderr)
    print(f"   Befehl: {command}", file=sys.stderr)
    print(f"   Sende Email an {EMAIL_TO}...", file=sys.stderr)

    # Server sicherstellen
    ensure_server_running()

    # Token generieren
    token = secrets.token_urlsafe(16)

    # Email senden
    sent = send_approval_email(token, command, tool_name)

    if not sent:
        print("[🔒] Email konnte nicht gesendet werden – Aktion BLOCKIERT", file=sys.stderr)
        # Blockieren: Claude Code beenden mit Non-Zero Exit
        result = {"decision": "block", "reason": "Email-Versand fehlgeschlagen"}
        print(json.dumps(result))
        sys.exit(1)

    print(f"[🔒] Email gesendet! Warte auf Bestätigung ({TIMEOUT//60} Min. Timeout)...", file=sys.stderr)

    # Auf Klick warten
    approved = wait_for_approval(token)

    if approved:
        print("[✓] Approved! Claude Code fährt fort.", file=sys.stderr)
        sys.exit(0)  # Weitermachen
    else:
        print("[✗] Denied oder Timeout – Aktion BLOCKIERT.", file=sys.stderr)
        sys.exit(1)  # Blockieren


if __name__ == "__main__":
    main()
