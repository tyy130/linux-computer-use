from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .driver import LinuxComputerUse
from .server import run as run_mcp


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="linux-computer-use")
    parser.add_argument("command", nargs="?", default="status", choices=["status", "mcp", "doctor", "smoke"])
    parser.add_argument("--json", action="store_true", help="Emit JSON for status/doctor")
    parser.add_argument("--version", action="version", version=f"linux-computer-use {__version__}")
    args = parser.parse_args(argv)

    if args.command == "mcp":
        run_mcp()
        return 0

    driver = LinuxComputerUse()
    if args.command == "smoke":
        result = driver.smoke_test()
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(f"linux-computer-use {__version__} smoke")
            for check in result["checks"]:
                suffix = f" — {check.get('error')}" if check.get("error") else ""
                print(f"  {'✓' if check.get('ok') else '✗'} {check['name']}{suffix}")
            if result.get("capture"):
                capture = result["capture"]
                print(f"capture: {capture['width']}x{capture['height']} window={capture['window_id']} {capture['title']}")
        return 0 if result["ok"] else 1

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
