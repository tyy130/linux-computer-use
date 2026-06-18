#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from linux_computer_use.driver import LinuxComputerUse  # noqa: E402


def launch_if_needed(driver: LinuxComputerUse) -> list[subprocess.Popen]:
    procs: list[subprocess.Popen] = []
    titles = "\n".join(w["title"] for w in driver.list_windows()["windows"])
    apps = "\n".join(w["app_name"] for w in driver.list_windows()["windows"])
    if "Coverage Dialog" not in titles:
        procs.append(subprocess.Popen([
            "zenity", "--info", "--title=Coverage Dialog", "--text=linux-computer-use coverage dialog", "--width=360"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(0.8)
    if "drawing" not in apps.lower() and Path("/usr/bin/drawing").exists():
        procs.append(subprocess.Popen(["drawing"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(1.5)
    return procs


def find_window(driver: LinuxComputerUse, label: str, needles: tuple[str, ...]) -> dict | None:
    for w in driver.list_windows()["windows"]:
        hay = f"{w['app_name']} {w['title']}".lower()
        if any(n.lower() in hay for n in needles):
            return w
    return None


def exercise(driver: LinuxComputerUse, label: str, needles: tuple[str, ...]) -> dict:
    rec = {"label": label, "ok": False, "window": None, "capture": None, "state": None, "error": None}
    try:
        w = find_window(driver, label, needles)
        if not w:
            raise RuntimeError(f"no matching window for {needles}")
        rec["window"] = {k: w[k] for k in ["window_id", "pid", "app_name", "title", "width", "height"]}
        shot = driver.screenshot(window_id=w["window_id"])
        rec["capture"] = {"width": shot["width"], "height": shot["height"]}
        state = driver.get_window_state(window_id=w["window_id"], max_elements=80)
        rec["state"] = {"summary": state["summary"], "elements": len(state["elements"])}
        rec["ok"] = shot["width"] > 0 and shot["height"] > 0 and len(state["elements"]) >= 1
    except Exception as exc:
        rec["error"] = str(exc)
    return rec


def main() -> int:
    driver = LinuxComputerUse()
    procs = launch_if_needed(driver)
    try:
        cases = [
            ("GTK dialog", ("coverage dialog", "zenity")),
            ("Chromium", ("chromium", "chrome")),
            ("Terminal", ("gnome-terminal", "terminal", "tdev | idle")),
            ("Drawing", ("drawing", "pencil", "unsaved file")),
        ]
        results = [exercise(driver, label, needles) for label, needles in cases]
        ok = all(r["ok"] for r in results)
        print(json.dumps({"ok": ok, "results": results}, indent=2))
        return 0 if ok else 1
    finally:
        for proc in procs:
            args = proc.args if isinstance(proc.args, list) else [str(proc.args)]
            if proc.poll() is None and "zenity" in " ".join(str(a) for a in args):
                proc.terminate()


if __name__ == "__main__":
    raise SystemExit(main())
