#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], timeout: int = 180) -> tuple[int, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    cp = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, check=False, env=env)
    return cp.returncode, (cp.stdout or cp.stderr).strip()


def main() -> int:
    print("# Agent-Native Linux Workstation Demo")
    steps = [
        ("Driver smoke test", [sys.executable, "-m", "linux_computer_use.cli", "smoke"]),
        ("Live GUI coverage", [sys.executable, "scripts/live_coverage.py"]),
        ("Machine cockpit sample", [sys.executable, str(Path.home() / ".hermes/skills/devops/machine-cockpit/scripts/machine_cockpit.py")]),
    ]
    ok = True
    for title, cmd in steps:
        print(f"\n## {title}")
        code, output = run(cmd)
        ok = ok and code == 0
        if title == "Machine cockpit sample":
            print("\n".join(output.splitlines()[:80]))
            if len(output.splitlines()) > 80:
                print("... truncated ...")
        elif output.startswith("{"):
            data = json.loads(output[output.find("{"):])
            print(json.dumps(data, indent=2)[:4000])
        else:
            print(output[:4000])
    print("\n## Result")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
