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
        self.display = os.environ.get("DISPLAY") or self._detect_x11_display()
        if self.display and not os.environ.get("DISPLAY"):
            # MCP servers launched by background agents often lose the desktop
            # environment even though the user's X11 socket is still available.
            # Export the inferred display so xdotool/scrot/import subprocesses
            # can talk to the same Cinnamon/X11 session.
            os.environ["DISPLAY"] = self.display
        if not os.environ.get("XAUTHORITY"):
            xauthority = Path.home() / ".Xauthority"
            if xauthority.exists():
                os.environ["XAUTHORITY"] = str(xauthority)
        self.wayland_display = os.environ.get("WAYLAND_DISPLAY")
        self.session_type = (os.environ.get("XDG_SESSION_TYPE") or "").lower()
        self._last_elements: dict[int, Element] = {}
        self._last_window: Window | None = None

    def _detect_x11_display(self) -> str | None:
        """Infer a local X11 display when launched without DISPLAY.

        This is intentionally conservative: it only considers local X sockets
        and returns the lowest numbered display. It does not invent a display on
        headless systems, so status remains honest when no desktop is present.
        """
        socket_dir = Path("/tmp/.X11-unix")
        try:
            displays = sorted(
                int(path.name[1:])
                for path in socket_dir.glob("X*")
                if path.name[1:].isdigit()
            )
        except OSError:
            return None
        return f":{displays[0]}" if displays else None

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

    def smoke_test(self) -> dict[str, Any]:
        """Run a read-only desktop smoke test for local/Cinnamon reliability."""
        status = self.status()
        windows = self.list_windows(on_screen_only=True)
        result: dict[str, Any] = {
            "ok": bool(status["ok"]),
            "status": status,
            "window_count": windows["count"],
            "capture": None,
            "checks": [],
        }
        result["checks"].append({"name": "driver_available", "ok": bool(status["ok"])})
        result["checks"].append({"name": "visible_windows", "ok": windows["count"] > 0})
        if windows["windows"]:
            target = next(
                (
                    w for w in windows["windows"]
                    if not any(token in f"{w.get('app_name', '')} {w.get('title', '')}".lower() for token in ("desktop", "muffin guard", "cinnamon"))
                ),
                windows["windows"][0],
            )
            try:
                shot = self.screenshot(window_id=target["window_id"])
                result["capture"] = {
                    "window_id": target["window_id"],
                    "title": target.get("title", ""),
                    "width": shot["width"],
                    "height": shot["height"],
                }
                result["checks"].append({"name": "window_capture", "ok": shot["width"] > 0 and shot["height"] > 0})
            except Exception as exc:
                result["checks"].append({"name": "window_capture", "ok": False, "error": str(exc)})
        result["ok"] = all(check.get("ok") for check in result["checks"])
        return result

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
            if not elements:
                elements = [Element(1, "window", target.title, target.x, target.y, target.width, target.height, target.app_name, target.pid)]
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
        x, y = self._resolve_point(element_index, x, y, window_id=window_id, pid=pid)
        return self._xdotool_mouse(["click", "1"], x, y, modifier=modifier)

    def double_click(self, **kwargs: Any) -> dict[str, Any]:
        x, y = self._resolve_point(kwargs.get("element_index"), kwargs.get("x"), kwargs.get("y"), window_id=kwargs.get("window_id"), pid=kwargs.get("pid"))
        return self._xdotool_mouse(["click", "--repeat", "2", "1"], x, y, modifier=kwargs.get("modifier"))

    def right_click(self, **kwargs: Any) -> dict[str, Any]:
        x, y = self._resolve_point(kwargs.get("element_index"), kwargs.get("x"), kwargs.get("y"), window_id=kwargs.get("window_id"), pid=kwargs.get("pid"))
        return self._xdotool_mouse(["click", "3"], x, y, modifier=kwargs.get("modifier"))

    def middle_click(self, **kwargs: Any) -> dict[str, Any]:
        x, y = self._resolve_point(kwargs.get("element_index"), kwargs.get("x"), kwargs.get("y"), window_id=kwargs.get("window_id"), pid=kwargs.get("pid"))
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
            self._activate_window(target.window_id)
            return {"ok": True, "message": f"raised {target.app_name} window {target.window_id}"}
        return {"ok": True, "message": f"targeted {target.app_name} window {target.window_id}; X11 actions may still require focus"}

    # Internals ---------------------------------------------------------------
    def _windows(self) -> list[Window]:
        windows = self._windows_xdotool()
        if windows:
            return windows
        return self._windows_wmctrl()

    def _windows_xdotool(self) -> list[Window]:
        if not shutil.which("xdotool"):
            return []
        try:
            ids = self._run(["xdotool", "search", "--onlyvisible", "--name", "."], check=False).stdout.split()
        except Exception:
            ids = []
        windows: list[Window] = []
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
        return windows

    def _windows_wmctrl(self) -> list[Window]:
        if not shutil.which("wmctrl"):
            return []
        out = self._run(["wmctrl", "-lpG"], check=False).stdout
        windows: list[Window] = []
        for z, line in enumerate(out.splitlines()):
            # 0x05400006  0 39585 1920 46 1920 1034 host title...
            parts = line.split(maxsplit=8)
            if len(parts) < 8:
                continue
            try:
                wid = int(parts[0], 16)
                pid = int(parts[2]) if parts[2].lstrip("-").isdigit() else 0
                x, y, width, height = (int(parts[i]) for i in range(3, 7))
            except ValueError:
                continue
            title = parts[8] if len(parts) > 8 else ""
            app = self._process_name(pid) or title.split(" - ")[-1] or "unknown"
            windows.append(Window(
                window_id=wid,
                pid=pid,
                app_name=app,
                title=title,
                x=x,
                y=y,
                width=width,
                height=height,
                z_index=z,
                is_on_screen=width > 0 and height > 0,
            ))
        return windows

    def _geometry(self, window_id: str) -> dict[str, int]:
        vals: dict[str, int] = {"x": 0, "y": 0, "width": 0, "height": 0}
        if shutil.which("xdotool"):
            out = self._run(["xdotool", "getwindowgeometry", "--shell", window_id], check=False).stdout
            for line in out.splitlines():
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.lower() in vals and re.fullmatch(r"-?\d+", v):
                    vals[k.lower()] = int(v)
            if vals["width"] > 0 and vals["height"] > 0:
                return vals
        for w in self._windows_wmctrl():
            if w.window_id == int(window_id):
                return {"x": w.x, "y": w.y, "width": w.width, "height": w.height}
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
        preferred = [
            w for w in windows
            if not any(token in f"{w.app_name} {w.title}".lower() for token in ("desktop", "muffin guard", "cinnamon"))
        ]
        return (preferred or windows)[0] if windows else None

    def _activate_window(self, window_id: int) -> None:
        if shutil.which("xdotool"):
            result = self._run(["xdotool", "windowactivate", str(window_id)], check=False)
            if result.returncode == 0:
                return
        if shutil.which("wmctrl"):
            self._run(["wmctrl", "-ia", hex(int(window_id))])
            return
        raise RuntimeError("No window activation command available; install xdotool or wmctrl")

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
                # AT-SPI app names do not always match /proc/<pid>/comm, so do
                # not hard-skip here. Geometry filtering against the target
                # window below is the reliable boundary.
                pass
            self._walk_accessible(app, elements, max_elements, app_name=app_name, pid=pid or 0)
            if len(elements) >= max_elements:
                break
        # Re-index after filtering invalid/unhelpful geometry.
        filtered = [e for e in elements if self._is_useful_element(e)]
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
                label = name or desc
                elem = Element(len(out) + 1, role, label, int(ext.x), int(ext.y), int(ext.width), int(ext.height), app_name, pid)
                if self._is_useful_element(elem):
                    out.append(elem)
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


    def _is_useful_element(self, e: Element) -> bool:
        role = e.role.lower().strip()
        label = (e.label or "").strip()
        ignored_roles = {"application", "desktop frame", "filler", "panel", "separator", "unknown"}
        if role in ignored_roles:
            return False
        if e.width <= 1 or e.height <= 1:
            return False
        if e.width > 5000 or e.height > 5000:
            return False
        # Large unlabeled containers create noisy SOM overlays and crowd out the
        # controls agents can actually use. Keep common interactive/text roles
        # even when unlabeled.
        interactive_markers = ("button", "menu", "item", "entry", "text", "combo", "check", "radio", "tab", "link", "slider", "spin")
        if not label and not any(marker in role for marker in interactive_markers):
            return False
        return True

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
        result = self._run(cmd, check=False)
        if result.returncode == 0 and path.exists() and path.stat().st_size > 0:
            return path
        if window_id is not None:
            try:
                return self._capture_window_fallback(window_id=window_id, out_path=path)
            except Exception as exc:
                raise RuntimeError(
                    f"Window capture failed via {cmd[0]} and fallback crop failed: {exc}"
                ) from exc
        raise RuntimeError(f"Screenshot command failed: {' '.join(cmd)}: {result.stderr.strip()}")

    def _capture_window_fallback(self, window_id: int, out_path: Path) -> Path:
        target = self._select_window(window_id=window_id)
        if target is None:
            raise RuntimeError(f"window {window_id} is not visible")
        root_path = Path(tempfile.mkstemp(prefix="linux-computer-use-root-", suffix=".png")[1])
        try:
            root_cmd = self._root_screenshot_command(root_path)
            if root_cmd is None:
                raise RuntimeError("no full-screen screenshot command available")
            # Raise before full-screen capture so occlusion is minimized. X11 can
            # still move focus, but this is an explicit fallback after precise
            # import -window capture failed.
            try:
                self._activate_window(window_id)
                time.sleep(0.15)
            except Exception:
                pass
            result = self._run(root_cmd, check=False)
            if result.returncode != 0 or not root_path.exists() or root_path.stat().st_size == 0:
                raise RuntimeError(f"full-screen screenshot failed: {result.stderr.strip()}")
            with Image.open(root_path).convert("RGBA") as img:
                left = max(0, target.x)
                top = max(0, target.y)
                right = min(img.width, target.x + target.width)
                bottom = min(img.height, target.y + target.height)
                if right <= left or bottom <= top:
                    raise RuntimeError(f"window geometry outside screenshot bounds: {target}")
                img.crop((left, top, right, bottom)).save(out_path)
            return out_path
        finally:
            try:
                root_path.unlink()
            except OSError:
                pass

    def _root_screenshot_command(self, path: Path) -> list[str] | None:
        if shutil.which("scrot"):
            return ["scrot", str(path)]
        if shutil.which("gnome-screenshot"):
            return ["gnome-screenshot", "-f", str(path)]
        if shutil.which("import"):
            return ["import", "-window", "root", str(path)]
        return None

    def _screenshot_command(self, path: Path | None = None, window_id: int | None = None) -> list[str] | None:
        if path is None:
            path = Path(os.devnull)
        # For a specific X11 window, ImageMagick import can target the id.
        # scrot -u only captures the currently focused window, which may not be
        # the requested one and can emit an empty file in headless/agent runs.
        if window_id and shutil.which("import"):
            return ["import", "-window", str(window_id), str(path)]
        return self._root_screenshot_command(path)

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

    def _resolve_point(self, element_index: int | None, x: int | None, y: int | None, window_id: int | None = None, pid: int | None = None) -> tuple[int, int]:
        if element_index is not None:
            elem = self._last_elements.get(int(element_index))
            if elem is None:
                raise ValueError(f"Unknown element_index {element_index}; call get_window_state first")
            self._guard_element_fresh(elem, window_id=window_id, pid=pid)
            return elem.center
        if x is None or y is None:
            raise ValueError("x/y or element_index required")
        return int(x), int(y)

    def _guard_element_fresh(self, elem: Element, window_id: int | None = None, pid: int | None = None) -> None:
        target = self._select_window(pid=pid, window_id=window_id) if (window_id is not None or pid is not None) else self._last_window
        if target is None:
            return
        if window_id is not None and int(window_id) != target.window_id:
            raise ValueError("Requested window_id does not match a visible window; refresh get_window_state")
        if pid is not None and int(pid) != target.pid:
            raise ValueError("Requested pid does not match a visible window; refresh get_window_state")
        if not self._element_intersects_window(elem, target):
            raise ValueError("Cached element no longer intersects target window; call get_window_state again")
        cx, cy = elem.center
        if not (target.x <= cx <= target.x + target.width and target.y <= cy <= target.y + target.height):
            raise ValueError("Cached element center is outside target window; call get_window_state again")

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
