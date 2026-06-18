from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont

try:  # pragma: no cover - import availability depends on desktop session
    import gi
    gi.require_version("Atspi", "2.0")
    from gi.repository import Atspi  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    Atspi = None  # type: ignore[assignment]


@dataclass
class Window:
    window_id: int
    pid: int
    app_name: str
    title: str
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    z_index: int = 0
    is_on_screen: bool = True


@dataclass
class Element:
    index: int
    role: str
    label: str
    x: int
    y: int
    width: int
    height: int
    app_name: str = ""
    pid: int = 0

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2


class LinuxComputerUse:
    """X11-first Linux desktop controller.

    This intentionally mirrors cua-driver's MCP tool names so Hermes can use it
    as a Linux backend with minimal adapter code. It is not a perfect macOS
    private-API clone: X11 actions use the real pointer/focus, and Wayland is
    capture-limited unless the compositor exposes automation portals.
    """

    def __init__(self) -> None:
        self.display = os.environ.get("DISPLAY")
        self.wayland_display = os.environ.get("WAYLAND_DISPLAY")
        self.session_type = (os.environ.get("XDG_SESSION_TYPE") or "").lower()
        self._last_elements: dict[int, Element] = {}
        self._last_window: Window | None = None

    def status(self) -> dict[str, Any]:
        commands = {
            name: bool(shutil.which(name))
            for name in ["xdotool", "scrot", "gnome-screenshot", "import", "wmctrl"]
        }
        return {
            "ok": self.is_available(),
            "session_type": self.session_type or ("wayland" if self.wayland_display else "x11" if self.display else "unknown"),
            "display": self.display,
            "wayland_display": self.wayland_display,
            "atspi": Atspi is not None,
            "commands": commands,
            "limitations": self.limitations(),
        }

    def limitations(self) -> list[str]:
        limits: list[str] = []
        if self.session_type == "wayland" or (self.wayland_display and not self.display):
            limits.append("Wayland blocks global synthetic input for normal apps; use X11/XWayland or compositor-specific portals for full control.")
        limits.append("Linux/X11 cannot currently match cua-driver's macOS background event delivery; actions may move the real pointer/focus.")
        return limits

    def is_available(self) -> bool:
        return bool((self.display or self.wayland_display) and self._screenshot_command())

    # Capture -----------------------------------------------------------------
    def list_windows(self, on_screen_only: bool = True) -> dict[str, Any]:
        windows = self._windows()
        if on_screen_only:
            windows = [w for w in windows if w.is_on_screen and w.width > 0 and w.height > 0]
        return {"windows": [w.__dict__ for w in windows], "count": len(windows)}

    def list_apps(self) -> dict[str, Any]:
        by_pid: dict[int, dict[str, Any]] = {}
        for w in self._windows():
            if w.pid <= 0:
                continue
            rec = by_pid.setdefault(w.pid, {"name": w.app_name, "pid": w.pid, "windows": 0, "titles": []})
            rec["windows"] += 1
            if w.title:
                rec["titles"].append(w.title)
        return {"apps": list(by_pid.values()), "count": len(by_pid)}

    def screenshot(self, window_id: int | None = None, format: str = "png", quality: int = 85) -> dict[str, Any]:
        image_path = self._capture_to_file(window_id=window_id)
        with Image.open(image_path) as img:
            width, height = img.size
        data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        try:
            image_path.unlink()
        except OSError:
            pass
        return {"image": data, "width": width, "height": height, "format": "png"}

    def get_window_state(self, pid: int | None = None, window_id: int | None = None, max_elements: int = 300) -> dict[str, Any]:
        target = self._select_window(pid=pid, window_id=window_id)
        self._last_window = target
        elements = self._collect_elements(pid=target.pid if target else pid, max_elements=max_elements)
        if target:
            elements = [
                e for e in elements
                if self._element_intersects_window(e, target)
                and e.width <= max(2, int(target.width * 1.2))
                and e.height <= max(2, int(target.height * 1.2))
            ]
        self._last_elements = {e.index: e for e in elements}
        tree = self._elements_markdown(elements, target)
        image_b64 = None
        width = height = 0
        if target:
            image_path = self._capture_to_file(window_id=target.window_id)
            overlay_path = self._draw_som(image_path, elements, target)
            with Image.open(overlay_path) as img:
                width, height = img.size
            image_b64 = base64.b64encode(overlay_path.read_bytes()).decode("ascii")
            for p in {image_path, overlay_path}:
                try:
                    p.unlink()
                except OSError:
                    pass
        return {
            "summary": f"✅ {target.app_name if target else 'Linux desktop'} — {len(elements)} elements",
            "tree": tree,
            "image": image_b64,
            "width": width,
            "height": height,
            "elements": [e.__dict__ for e in elements],
        }

    # Actions -----------------------------------------------------------------
    def click(self, pid: int | None = None, window_id: int | None = None, element_index: int | None = None, x: int | None = None, y: int | None = None, modifier: list[str] | None = None) -> dict[str, Any]:
        x, y = self._resolve_point(element_index, x, y)
        return self._xdotool_mouse(["click", "1"], x, y, modifier=modifier)

    def double_click(self, **kwargs: Any) -> dict[str, Any]:
        x, y = self._resolve_point(kwargs.get("element_index"), kwargs.get("x"), kwargs.get("y"))
        return self._xdotool_mouse(["click", "--repeat", "2", "1"], x, y, modifier=kwargs.get("modifier"))

    def right_click(self, **kwargs: Any) -> dict[str, Any]:
        x, y = self._resolve_point(kwargs.get("element_index"), kwargs.get("x"), kwargs.get("y"))
        return self._xdotool_mouse(["click", "3"], x, y, modifier=kwargs.get("modifier"))

    def middle_click(self, **kwargs: Any) -> dict[str, Any]:
        x, y = self._resolve_point(kwargs.get("element_index"), kwargs.get("x"), kwargs.get("y"))
        return self._xdotool_mouse(["click", "2"], x, y, modifier=kwargs.get("modifier"))

    def drag(self, from_element: int | None = None, to_element: int | None = None, from_x: int | None = None, from_y: int | None = None, to_x: int | None = None, to_y: int | None = None, **_: Any) -> dict[str, Any]:
        sx, sy = self._resolve_point(from_element, from_x, from_y)
        tx, ty = self._resolve_point(to_element, to_x, to_y)
        self._run(["xdotool", "mousemove", str(sx), str(sy), "mousedown", "1", "mousemove", str(tx), str(ty), "mouseup", "1"])
        return {"ok": True, "message": f"dragged ({sx},{sy}) -> ({tx},{ty})"}

    def scroll(self, direction: str, amount: int = 3, element_index: int | None = None, x: int | None = None, y: int | None = None, **_: Any) -> dict[str, Any]:
        if element_index is not None or (x is not None and y is not None):
            px, py = self._resolve_point(element_index, x, y)
            self._run(["xdotool", "mousemove", str(px), str(py)])
        button = {"up": "4", "down": "5", "left": "6", "right": "7"}.get(direction, "5")
        amount = max(1, min(int(amount), 50))
        self._run(["xdotool", "click", "--repeat", str(amount), button])
        return {"ok": True, "message": f"scrolled {direction} x{amount}"}

    def type_text(self, pid: int | None = None, text: str = "") -> dict[str, Any]:
        self._run(["xdotool", "type", "--clearmodifiers", "--", text])
        return {"ok": True, "message": f"typed {len(text)} characters"}

    def press_key(self, key: str, **_: Any) -> dict[str, Any]:
        self._run(["xdotool", "key", self._key_name(key)])
        return {"ok": True, "message": f"pressed {key}"}

    def hotkey(self, keys: list[str], **_: Any) -> dict[str, Any]:
        combo = "+".join(self._key_name(k) for k in keys)
        self._run(["xdotool", "key", combo])
        return {"ok": True, "message": f"pressed {combo}"}

    def set_value(self, element_index: int, value: str, **_: Any) -> dict[str, Any]:
        # Generic fallback: click element, select existing text, type replacement.
        x, y = self._resolve_point(element_index, None, None)
        self._xdotool_mouse(["click", "1"], x, y)
        self.hotkey(["ctrl", "a"])
        self.type_text(text=value)
        return {"ok": True, "message": f"set element {element_index} via click+type fallback"}

    def focus_app(self, app: str, raise_window: bool = False) -> dict[str, Any]:
        matches = [w for w in self._windows() if app.lower() in f"{w.app_name} {w.title}".lower()]
        if not matches:
            return {"ok": False, "message": f"No window found for {app!r}"}
        target = matches[0]
        self._last_window = target
        if raise_window:
            self._run(["xdotool", "windowactivate", str(target.window_id)])
            return {"ok": True, "message": f"raised {target.app_name} window {target.window_id}"}
        return {"ok": True, "message": f"targeted {target.app_name} window {target.window_id}; X11 actions may still require focus"}

    # Internals ---------------------------------------------------------------
    def _windows(self) -> list[Window]:
        if shutil.which("xdotool"):
            try:
                ids = self._run(["xdotool", "search", "--onlyvisible", "--name", "."], check=False).stdout.split()
            except Exception:
                ids = []
            windows = []
            for z, wid_text in enumerate(ids):
                try:
                    wid = int(wid_text)
                    title = self._run(["xdotool", "getwindowname", wid_text], check=False).stdout.strip()
                    pid_out = self._run(["xdotool", "getwindowpid", wid_text], check=False).stdout.strip()
                    pid = int(pid_out) if pid_out.isdigit() else 0
                    geom = self._geometry(wid_text)
                    app = self._process_name(pid) or title.split(" - ")[-1] or "unknown"
                    windows.append(Window(
                        window_id=wid,
                        pid=pid,
                        app_name=app,
                        title=title,
                        x=geom["x"],
                        y=geom["y"],
                        width=geom["width"],
                        height=geom["height"],
                        z_index=z,
                    ))
                except Exception:
                    continue
            if windows:
                return windows
        return []

    def _geometry(self, window_id: str) -> dict[str, int]:
        out = self._run(["xdotool", "getwindowgeometry", "--shell", window_id], check=False).stdout
        vals: dict[str, int] = {"x": 0, "y": 0, "width": 0, "height": 0}
        for line in out.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k.lower() in vals and re.fullmatch(r"-?\d+", v):
                vals[k.lower()] = int(v)
        return vals

    def _select_window(self, pid: int | None = None, window_id: int | None = None) -> Window | None:
        windows = self._windows()
        if window_id is not None:
            for w in windows:
                if w.window_id == int(window_id):
                    return w
        if pid is not None:
            for w in windows:
                if w.pid == int(pid):
                    return w
        return windows[0] if windows else None

    def _collect_elements(self, pid: int | None = None, max_elements: int = 300) -> list[Element]:
        if Atspi is None:
            return []
        elements: list[Element] = []
        desktop = Atspi.get_desktop(0)
        target_name = self._process_name(pid) if pid else None
        for i in range(desktop.get_child_count()):
            app = desktop.get_child_at_index(i)
            app_name = self._safe(lambda: app.get_name(), "") or ""
            if target_name and target_name.lower() not in app_name.lower():
                # Some apps expose a different accessible app name; keep walking if no target yet.
                pass
            self._walk_accessible(app, elements, max_elements, app_name=app_name, pid=pid or 0)
            if len(elements) >= max_elements:
                break
        # Re-index after filtering invalid geometry.
        filtered = [e for e in elements if e.width > 1 and e.height > 1]
        for idx, elem in enumerate(filtered[:max_elements], start=1):
            elem.index = idx
        return filtered[:max_elements]

    def _walk_accessible(self, obj: Any, out: list[Element], max_elements: int, app_name: str, pid: int, depth: int = 0) -> None:
        if len(out) >= max_elements or depth > 12:
            return
        try:
            role = obj.get_role_name()
            name = obj.get_name() or ""
            desc = obj.get_description() or ""
            comp = obj.get_component_iface()
            if comp is not None:
                ext = comp.get_extents(Atspi.CoordType.SCREEN)  # type: ignore[union-attr]
                if ext.width > 1 and ext.height > 1 and role not in {"filler", "panel", "application"}:
                    out.append(Element(len(out) + 1, role, name or desc, int(ext.x), int(ext.y), int(ext.width), int(ext.height), app_name, pid))
        except Exception:
            pass
        try:
            count = obj.get_child_count()
            for i in range(min(count, 200)):
                child = obj.get_child_at_index(i)
                if child is not None:
                    self._walk_accessible(child, out, max_elements, app_name, pid, depth + 1)
        except Exception:
            return

    def _element_intersects_window(self, e: Element, w: Window) -> bool:
        return e.x + e.width >= w.x and e.x <= w.x + w.width and e.y + e.height >= w.y and e.y <= w.y + w.height

    def _elements_markdown(self, elements: Iterable[Element], target: Window | None) -> str:
        lines = []
        if target:
            lines.append(f'AXWindow "{target.title}" [{target.x},{target.y},{target.width},{target.height}]')
        for e in elements:
            label = (e.label or "").replace("\n", " ")[:80]
            lines.append(f'  - [{e.index}] AX{e.role.title().replace(" ", "")} "{label}" [{e.x},{e.y},{e.width},{e.height}]')
        return "\n".join(lines)

    def _capture_to_file(self, window_id: int | None = None) -> Path:
        path = Path(tempfile.mkstemp(prefix="linux-computer-use-", suffix=".png")[1])
        cmd = self._screenshot_command(path, window_id)
        if cmd is None:
            raise RuntimeError("No screenshot command available; install scrot, gnome-screenshot, or ImageMagick import")
        self._run(cmd)
        return path

    def _screenshot_command(self, path: Path | None = None, window_id: int | None = None) -> list[str] | None:
        if path is None:
            path = Path(os.devnull)
        # For a specific X11 window, ImageMagick import can target the id.
        # scrot -u only captures the currently focused window, which may not be
        # the requested one and can emit an empty file in headless/agent runs.
        if window_id and shutil.which("import"):
            return ["import", "-window", str(window_id), str(path)]
        if shutil.which("scrot"):
            return ["scrot", str(path)]
        if shutil.which("gnome-screenshot"):
            return ["gnome-screenshot", "-f", str(path)]
        if shutil.which("import"):
            return ["import", "-window", "root", str(path)]
        return None

    def _draw_som(self, image_path: Path, elements: list[Element], target: Window) -> Path:
        out_path = image_path.with_name(image_path.stem + "-som.png")
        with Image.open(image_path).convert("RGBA") as img:
            draw = ImageDraw.Draw(img)
            font = ImageFont.load_default()
            for e in elements:
                # Window screenshots are local to target top-left; full-screen scrot -u still returns active window pixels.
                rx = max(0, e.x - target.x)
                ry = max(0, e.y - target.y)
                if rx >= img.width or ry >= img.height:
                    continue
                text = str(e.index)
                bbox = draw.textbbox((rx, ry), text, font=font)
                pad = 3
                rect = (rx, ry, bbox[2] + pad * 2, bbox[3] + pad * 2)
                draw.rectangle(rect, fill=(255, 214, 10, 230), outline=(0, 0, 0, 255), width=1)
                draw.text((rx + pad, ry + pad), text, fill=(0, 0, 0, 255), font=font)
                draw.rectangle((rx, ry, min(img.width - 1, rx + e.width), min(img.height - 1, ry + e.height)), outline=(255, 214, 10, 180), width=1)
            img.save(out_path)
        return out_path

    def _resolve_point(self, element_index: int | None, x: int | None, y: int | None) -> tuple[int, int]:
        if element_index is not None:
            elem = self._last_elements.get(int(element_index))
            if elem is None:
                raise ValueError(f"Unknown element_index {element_index}; call get_window_state first")
            return elem.center
        if x is None or y is None:
            raise ValueError("x/y or element_index required")
        return int(x), int(y)

    def _xdotool_mouse(self, click_args: list[str], x: int, y: int, modifier: list[str] | None = None) -> dict[str, Any]:
        cmd = ["xdotool", "mousemove", str(x), str(y)]
        if modifier:
            for mod in modifier:
                cmd += ["keydown", self._key_name(mod)]
        cmd += click_args
        if modifier:
            for mod in reversed(modifier):
                cmd += ["keyup", self._key_name(mod)]
        self._run(cmd)
        return {"ok": True, "message": f"clicked at ({x},{y})"}

    def _key_name(self, key: str) -> str:
        mapping = {
            "cmd": "Super_L", "command": "Super_L", "meta": "Super_L",
            "ctrl": "ctrl", "control": "ctrl", "option": "alt", "alt": "alt",
            "return": "Return", "enter": "Return", "escape": "Escape", "esc": "Escape",
            "backspace": "BackSpace", "delete": "Delete", "tab": "Tab", "space": "space",
        }
        return mapping.get(str(key).lower(), str(key))

    def _process_name(self, pid: int | None) -> str:
        if not pid:
            return ""
        try:
            return Path(f"/proc/{pid}/comm").read_text().strip()
        except OSError:
            return ""

    def _run(self, cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, text=True, capture_output=True, check=check)

    def _safe(self, fn: Any, default: Any) -> Any:
        try:
            return fn()
        except Exception:
            return default
