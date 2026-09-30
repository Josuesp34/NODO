#!/usr/bin/env python3
"""Run the guarded 70-athlete corpus against the isolated local demo."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    state = ROOT / ".local/nodo-demo"
    config = dict(
        line.split("=", 1)
        for line in (state / ".env").read_text().splitlines()
        if "=" in line
    )
    environment = os.environ.copy()
    environment.update(
        {
            "ENVIRONMENT": "development",
            "NODO_SYNTHETIC_QA": "1",
            "DATABASE_URL": f"postgresql+asyncpg://nodo_demo:{config['DEMO_DB_PASSWORD']}@127.0.0.1:{int(config['DEMO_DB_PORT'])}/nodo_demo",
        }
    )
    script = str(ROOT / "ops/qa_corpus.py")
    for action in ("seed", "benchmark"):
        subprocess.run(
            [
                sys.executable,
                script,
                action,
                "--url",
                f"http://127.0.0.1:{int(config['DEMO_API_PORT'])}/api/v1",
                "--output",
                str(state / f"qa-{action}.json"),
            ],
            cwd=ROOT,
            env=environment,
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
