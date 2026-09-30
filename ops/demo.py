#!/usr/bin/env python3
"""Demo aislada y repetible; sólo requiere Python 3 y Docker Compose."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local" / "nodo-demo"


def prepare():
    STATE.mkdir(parents=True, exist_ok=True, mode=0o700)
    (STATE / "postgres").mkdir(exist_ok=True)
    files = STATE / "files"
    files.mkdir(exist_ok=True, mode=0o700)
    env_file = STATE / ".env"
    suffix = hashlib.sha256(str(ROOT).encode()).hexdigest()[:10]
    if not env_file.exists():
        db_password = secrets.token_urlsafe(32)
        values = {
            "DEMO_DB_PASSWORD": db_password,
            "DEMO_DATABASE_URL": f"postgresql+asyncpg://nodo_demo:{db_password}@postgres:5432/nodo_demo",
            "DEMO_LOGIN_PASSWORD": secrets.token_urlsafe(24),
            "DEMO_API_IMAGE": f"nodo-demo-api:{suffix}",
            "DEMO_PWA_IMAGE": f"nodo-demo-pwa:{suffix}",
            "DEMO_DB_PORT": os.environ.get("NODO_DEMO_DB_PORT", "55432"),
            "DEMO_API_PORT": os.environ.get("NODO_DEMO_API_PORT", "8800"),
            "DEMO_WEB_PORT": os.environ.get("NODO_DEMO_WEB_PORT", "3300"),
        }
        with env_file.open("x") as stream:
            os.chmod(env_file, 0o600)
            stream.write("\n".join(f"{key}={value}" for key, value in values.items()) + "\n")
    values = dict(line.split("=", 1) for line in env_file.read_text().splitlines() if "=" in line)
    credentials = STATE / "credentials.json"
    credentials.write_text(json.dumps({
        "password": values["DEMO_LOGIN_PASSWORD"],
        "accounts": ["admin-demo@example.com", "coach-demo@example.com", "athlete-demo@example.com", "solo-demo@example.com", "dual-demo@example.com"],
        "url": f"http://127.0.0.1:{values['DEMO_WEB_PORT']}",
    }, indent=2) + "\n")
    os.chmod(credentials, 0o600)
    return ["docker", "compose", "--project-name", f"nodo-demo-{suffix}", "--env-file", str(env_file), "-f", str(ROOT / "compose.demo.yml")], values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["up", "stop", "status", "seed", "restart-worker", "logs"])
    args = parser.parse_args()
    compose, values = prepare()
    commands = {
        "up": [[*compose, "build"], [*compose, "up", "-d", "--wait", "api", "worker", "pwa"], [*compose, "run", "--rm", "seed"]],
        "stop": [[*compose, "stop"]],
        "status": [[*compose, "ps"]],
        "seed": [[*compose, "run", "--rm", "seed"]],
        "restart-worker": [[*compose, "restart", "worker"]],
        "logs": [[*compose, "logs", "--tail", "50", "migrate", "api", "worker", "pwa"]],
    }
    try:
        for command in commands[args.action]:
            subprocess.run(command, cwd=ROOT, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("La demo no completó la acción; comprobar Docker y los logs. Los datos se conservan.", file=sys.stderr)
        return 1
    if args.action in {"up", "seed"}:
        print(f"Demo: http://127.0.0.1:{values['DEMO_WEB_PORT']}")
        print(f"Credenciales sintéticas locales: {STATE / 'credentials.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
