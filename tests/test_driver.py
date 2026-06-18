from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from linux_computer_use.driver import Element, LinuxComputerUse, Window


def test_key_name_maps_common_aliases() -> None:
    driver = LinuxComputerUse()
    assert driver._key_name("return") == "Return"
    assert driver._key_name("cmd") == "Super_L"
    assert driver._key_name("ctrl") == "ctrl"


def test_resolve_point_prefers_cached_element_center() -> None:
    driver = LinuxComputerUse()
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
        cp = Mock()
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
