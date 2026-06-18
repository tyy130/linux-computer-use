from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from linux_computer_use.driver import Element, LinuxComputerUse, Window


def test_key_name_maps_common_aliases() -> None:
    driver = LinuxComputerUse()
    assert driver._key_name("return") == "Return"
    assert driver._key_name("cmd") == "Super_L"
    assert driver._key_name("ctrl") == "ctrl"


def test_resolve_point_prefers_cached_element_center() -> None:
    driver = LinuxComputerUse()
    driver._last_window = Window(11, 22, "demo", "Demo", 0, 0, 100, 100)
    driver._last_elements = {7: Element(7, "push button", "OK", 10, 20, 30, 40)}
    assert driver._resolve_point(7, None, None) == (25, 40)


def test_elements_markdown_matches_cua_parse_shape() -> None:
    driver = LinuxComputerUse()
    window = Window(window_id=11, pid=22, app_name="demo", title="Demo", x=0, y=0, width=800, height=600)
    text = driver._elements_markdown([Element(1, "push button", "Save", 10, 20, 30, 40)], window)
    assert 'AXWindow "Demo"' in text
    assert '- [1] AXPushButton "Save" [10,20,30,40]' in text


def test_list_windows_parses_xdotool_shell_geometry(monkeypatch) -> None:
    driver = LinuxComputerUse()

    def fake_run(cmd: list[str], check: bool = True):
        joined = " ".join(cmd)
        cp = Mock(returncode=0)
        if "search --onlyvisible" in joined:
            cp.stdout = "123\n"
        elif "getwindowname" in joined:
            cp.stdout = "Demo Window\n"
        elif "getwindowpid" in joined:
            cp.stdout = "456\n"
        elif "getwindowgeometry --shell" in joined:
            cp.stdout = "X=1\nY=2\nWIDTH=300\nHEIGHT=200\n"
        else:
            cp.stdout = ""
        return cp

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}" if name == "xdotool" else None)
    monkeypatch.setattr(driver, "_run", fake_run)
    monkeypatch.setattr(driver, "_process_name", lambda pid: "demo")

    windows = driver._windows()
    assert len(windows) == 1
    assert windows[0].window_id == 123
    assert windows[0].pid == 456
    assert windows[0].app_name == "demo"
    assert windows[0].width == 300


def test_list_windows_falls_back_to_wmctrl(monkeypatch) -> None:
    driver = LinuxComputerUse()

    def fake_which(name: str):
        return f"/usr/bin/{name}" if name == "wmctrl" else None

    def fake_run(cmd: list[str], check: bool = True):
        cp = Mock(returncode=0)
        cp.stdout = "0x05400006  0 39585 1920 46 1920 1034 T-Notebook tdev | idle | running: hermes\n"
        return cp

    monkeypatch.setattr("shutil.which", fake_which)
    monkeypatch.setattr(driver, "_run", fake_run)
    monkeypatch.setattr(driver, "_process_name", lambda pid: "hermes")

    windows = driver._windows()
    assert len(windows) == 1
    assert windows[0].window_id == int("0x05400006", 16)
    assert windows[0].pid == 39585
    assert windows[0].x == 1920
    assert windows[0].width == 1920
    assert windows[0].app_name == "hermes"


def test_driver_infers_x11_display_for_agent_processes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("XAUTHORITY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".Xauthority").write_text("cookie")

    socket_dir = tmp_path / "x11"
    socket_dir.mkdir()
    (socket_dir / "X0").touch()
    original_glob = Path.glob

    def fake_glob(self: Path, pattern: str):
        if str(self) == "/tmp/.X11-unix" and pattern == "X*":
            return original_glob(socket_dir, pattern)
        return original_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", fake_glob)
    driver = LinuxComputerUse()

    assert driver.display == ":0"
    assert driver._detect_x11_display() == ":0"
    assert driver.status()["display"] == ":0"


def test_smoke_test_reports_capture(monkeypatch) -> None:
    driver = LinuxComputerUse()
    monkeypatch.setattr(driver, "status", lambda: {"ok": True})
    monkeypatch.setattr(driver, "list_windows", lambda on_screen_only=True: {"count": 1, "windows": [{"window_id": 123, "title": "Demo"}]})
    monkeypatch.setattr(driver, "screenshot", lambda window_id=None: {"width": 640, "height": 480, "image": ""})

    result = driver.smoke_test()

    assert result["ok"] is True
    assert result["window_count"] == 1
    assert result["capture"]["window_id"] == 123


def test_stale_element_guard_rejects_outside_window() -> None:
    driver = LinuxComputerUse()
    driver._last_window = Window(11, 22, "demo", "Demo", 0, 0, 100, 100)
    driver._last_elements = {1: Element(1, "push button", "OK", 500, 500, 30, 30)}

    with pytest.raises(ValueError, match="no longer intersects"):
        driver._resolve_point(1, None, None)


def test_useful_element_filter_keeps_controls_and_drops_noise() -> None:
    driver = LinuxComputerUse()
    assert driver._is_useful_element(Element(1, "push button", "Save", 1, 1, 50, 20))
    assert driver._is_useful_element(Element(1, "text", "", 1, 1, 50, 20))
    assert not driver._is_useful_element(Element(1, "filler", "", 1, 1, 50, 20))
    assert not driver._is_useful_element(Element(1, "section", "", 1, 1, 50, 20))


def test_get_window_state_adds_window_fallback_when_atspi_empty(monkeypatch) -> None:
    driver = LinuxComputerUse()
    window = Window(11, 22, "demo", "Demo", 0, 0, 100, 100)
    monkeypatch.setattr(driver, "_select_window", lambda pid=None, window_id=None: window)
    monkeypatch.setattr(driver, "_collect_elements", lambda pid=None, max_elements=300: [])
    monkeypatch.setattr(driver, "_capture_to_file", lambda window_id=None: Path("/tmp/nonexistent.png"))
    monkeypatch.setattr(driver, "_draw_som", lambda image_path, elements, target: image_path)

    def fake_open(path):
        class Img:
            size = (100, 100)
            def __enter__(self): return self
            def __exit__(self, *args): return None
        return Img()

    monkeypatch.setattr("linux_computer_use.driver.Image.open", fake_open)
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"png")
    monkeypatch.setattr(Path, "unlink", lambda self: None)

    result = driver.get_window_state(window_id=11)

    assert result["summary"] == "✅ demo — 1 elements"
    assert result["elements"][0]["role"] == "window"


def test_capture_to_file_falls_back_to_root_crop(monkeypatch, tmp_path: Path) -> None:
    driver = LinuxComputerUse()
    target = Window(11, 22, "demo", "Demo", 10, 20, 50, 40)
    monkeypatch.setattr(driver, "_select_window", lambda pid=None, window_id=None: target)
    monkeypatch.setattr(driver, "_activate_window", lambda window_id: None)

    root = tmp_path / "root.png"
    Image.new("RGBA", (120, 100), (255, 0, 0, 255)).save(root)

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], check: bool = True):
        calls.append(cmd)
        cp = Mock()
        if cmd[0] == "import" and "11" in cmd:
            cp.returncode = 1
            cp.stderr = "weird window"
        else:
            cp.returncode = 0
            cp.stderr = ""
            Path(cmd[-1]).write_bytes(root.read_bytes())
        return cp

    monkeypatch.setattr(driver, "_run", fake_run)
    monkeypatch.setattr(driver, "_screenshot_command", lambda path, window_id=None: ["import", "-window", str(window_id), str(path)])
    monkeypatch.setattr(driver, "_root_screenshot_command", lambda path: ["scrot", str(path)])

    out = driver._capture_to_file(window_id=11)

    with Image.open(out) as cropped:
        assert cropped.size == (50, 40)
    assert calls[0][0] == "import"
    assert calls[1][0] == "scrot"
