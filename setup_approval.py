#!/usr/bin/env python3
"""
Setup Script für Claude Code Email Approval System
Führe aus: python setup_approval.py
"""

import os
import json
import shutil
import subprocess
import sys
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude"
HOOKS_DIR  = CLAUDE_DIR / "hooks"
SCRIPTS_DIR = Path.home() / "claude-approval"

def print_step(n, text):
    print(f"\n[{n}] {text}")
    print("─" * 50)

def print_ok(text):
    print(f"    ✓ {text}")

def print_warn(text):
    print(f"    ⚠ {text}")


def main():
    print("\n" + "═" * 50)
    print("  Claude Code Email Approval Setup")
    print("═" * 50)

    # ─── Schritt 1: Verzeichnisse ─────────────────────────────────────────────
    print_step(1, "Verzeichnisse erstellen")

    SCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    (Path.home() / ".claude_approvals").mkdir(exist_ok=True)
    print_ok(f"Scripts:   {SCRIPTS_DIR}")
    print_ok(f"Hooks:     {HOOKS_DIR}")
    print_ok(f"Approvals: {Path.home() / '.claude_approvals'}")

    # ─── Schritt 2: Scripts kopieren ──────────────────────────────────────────
    print_step(2, "Scripts installieren")

    script_dir = Path(__file__).parent
    for script in ["claude_approval_hook.py", "approval_server.py"]:
        src = script_dir / script
        dst = SCRIPTS_DIR / script
        if src.exists():
            shutil.copy2(src, dst)
            print_ok(f"Kopiert: {script}")
        else:
            print_warn(f"Nicht gefunden: {script} (stelle sicher dass alle 3 Dateien im gleichen Ordner sind)")

    # ─── Schritt 3: Email-Konfiguration ───────────────────────────────────────
    print_step(3, "Gmail Konfiguration")
    print()
    print("    Du brauchst ein Gmail App-Passwort (nicht dein normales Passwort!):")
    print("    → https://myaccount.google.com/apppasswords")
    print("    → App: 'Mail' | Gerät: 'Windows Computer'")
    print()

    email_from = input("    Deine Gmail-Adresse: ").strip()
    email_pass = input("    App-Passwort (16 Zeichen): ").strip()
    email_to   = input(f"    Email-Empfänger [{email_from}]: ").strip() or email_from

    # ─── Schritt 4: ngrok Frage ───────────────────────────────────────────────
    print_step(4, "Erreichbarkeit von unterwegs")
    print()
    print("    Für den Approve-Link auf deinem Handy gibt es zwei Optionen:")
    print("    [1] ngrok (empfohlen) – öffentliche URL, funktioniert überall")
    print("    [2] Nur lokal – funktioniert nur wenn du im gleichen Netz bist")
    print()

    choice = input("    Wahl [1/2]: ").strip()
    base_url = "http://localhost:8742"

    if choice == "1":
        print()
        print("    ngrok Setup:")
        print("    → https://ngrok.com/download (kostenlos)")
        print("    → Nach Installation: ngrok http 8742")
        print("    → Die angezeigte https://xxx.ngrok.io URL hier eingeben")
        print()
        ngrok_url = input("    ngrok URL (oder Enter für später): ").strip()
        if ngrok_url:
            base_url = ngrok_url.rstrip("/")

    # ─── Schritt 5: Umgebungsvariablen setzen ─────────────────────────────────
    print_step(5, "Umgebungsvariablen konfigurieren")

    env_content = f"""
# Claude Code Email Approval
APPROVAL_EMAIL_FROM={email_from}
APPROVAL_EMAIL_PASSWORD={email_pass}
APPROVAL_EMAIL_TO={email_to}
APPROVAL_BASE_URL={base_url}
APPROVAL_TIMEOUT=300
"""

    env_file = SCRIPTS_DIR / ".env"
    env_file.write_text(env_content.strip())
    print_ok(f"Gespeichert: {env_file}")

    # PowerShell Profil für persistente Env-Vars (Windows)
    ps_profile = Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
    ps_profile.parent.mkdir(parents=True, exist_ok=True)

    ps_env = f"""
# Claude Code Email Approval
$env:APPROVAL_EMAIL_FROM = "{email_from}"
$env:APPROVAL_EMAIL_PASSWORD = "{email_pass}"
$env:APPROVAL_EMAIL_TO = "{email_to}"
$env:APPROVAL_BASE_URL = "{base_url}"
$env:APPROVAL_TIMEOUT = "300"
"""

    # Anhängen falls Profil existiert
    with open(ps_profile, "a") as f:
        f.write(ps_env)
    print_ok(f"PowerShell Profil aktualisiert: {ps_profile}")

    # ─── Schritt 6: Claude Code Hook registrieren ─────────────────────────────
    print_step(6, "Claude Code Hook registrieren")

    settings_file = CLAUDE_DIR / "settings.json"

    if settings_file.exists():
        with open(settings_file) as f:
            settings = json.load(f)
    else:
        settings = {}

    hook_command = f"{sys.executable} {SCRIPTS_DIR / 'claude_approval_hook.py'}"

    if "hooks" not in settings:
        settings["hooks"] = {}

    settings["hooks"]["PreToolUse"] = [
        {
            "matcher": "Bash",
            "hooks": [
                {
                    "type": "command",
                    "command": hook_command
                }
            ]
        }
    ]

    # Auto-approve für nicht-kritische Aktionen
    if "permissions" not in settings:
        settings["permissions"] = {}

    settings["permissions"]["allow"] = [
        "Read",
        "Write",
        "Edit",
        "MultiEdit",
        "NotebookRead",
        "NotebookEdit",
        "WebFetch",
        "WebSearch",
        "TodoRead",
        "TodoWrite",
        "Glob",
        "Grep",
        "LS"
    ]

    with open(settings_file, "w") as f:
        json.dump(settings, f, indent=2)

    print_ok(f"Hook registriert in: {settings_file}")
    print_ok("Auto-approve für Read/Write/Edit aktiviert")

    # ─── Fertig ───────────────────────────────────────────────────────────────
    print("\n" + "═" * 50)
    print("  ✓ Setup abgeschlossen!")
    print("═" * 50)
    print()
    print("  Was jetzt:")
    print("  1. PowerShell neu starten (Umgebungsvariablen laden)")
    print("  2. Claude Code starten: claude")
    if choice == "1" and not ngrok_url:
        print("  3. ngrok starten: ngrok http 8742")
        print("     Dann BASE_URL in PowerShell Profil aktualisieren")
    print()
    print("  Test: Bitte Claude Code 'git push' auszuführen")
    print("        → Du solltest eine Email bekommen!")
    print()


if __name__ == "__main__":
    main()
