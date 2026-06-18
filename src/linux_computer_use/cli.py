from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .driver import LinuxComputerUse
from .server import run as run_mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="linux-computer-use")
    parser.add_argument("command", nargs="?", default="status", choices=["status", "mcp", "doctor"])
    parser.add_argument("--json", action="store_true", help="Emit JSON for status/doctor")
    parser.add_argument("--version", action="version", version=f"linux-computer-use {__version__}")
    args = parser.parse_args(argv)

    if args.command == "mcp":
        run_mcp()
        return 0

    driver = LinuxComputerUse()
    status = driver.status()
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        print(f"linux-computer-use {__version__}")
        print(f"ok: {status['ok']}")
        print(f"session: {status['session_type']} DISPLAY={status.get('display')} WAYLAND_DISPLAY={status.get('wayland_display')}")
        print(f"at-spi: {status['atspi']}")
        print("commands:")
        for name, available in status["commands"].items():
            print(f"  {'✓' if available else '✗'} {name}")
        if status["limitations"]:
            print("limitations:")
            for item in status["limitations"]:
                print(f"  - {item}")
    return 0 if status["ok"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main(sys.argv[1:]))
