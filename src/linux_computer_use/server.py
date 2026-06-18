from __future__ import annotations

import base64
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.utilities.types import Image

from .driver import LinuxComputerUse

mcp = FastMCP("linux-computer-use")
driver = LinuxComputerUse()


@mcp.tool()
def status() -> dict[str, Any]:
    """Return driver readiness, detected session type, and limitations."""
    return driver.status()


@mcp.tool()
def list_windows(on_screen_only: bool = True) -> dict[str, Any]:
    """List visible desktop windows."""
    return driver.list_windows(on_screen_only=on_screen_only)


@mcp.tool()
def list_apps() -> dict[str, Any]:
    """List running apps with visible windows."""
    return driver.list_apps()


@mcp.tool()
def screenshot(window_id: int | None = None, format: str = "png", quality: int = 85) -> Any:
    """Capture a screenshot as an MCP image plus metadata text."""
    result = driver.screenshot(window_id=window_id, format=format, quality=quality)
    image = Image(data=base64.b64decode(result["image"]), format="png")
    return [{"width": result["width"], "height": result["height"], "format": "png"}, image]


@mcp.tool()
def get_window_state(pid: int | None = None, window_id: int | None = None, max_elements: int = 300) -> Any:
    """Return a cua-compatible accessibility/SOM tree and screenshot."""
    result = driver.get_window_state(pid=pid, window_id=window_id, max_elements=max_elements)
    text = result["summary"] + ("\n" + result["tree"] if result.get("tree") else "")
    parts: list[Any] = [text]
    if result.get("image"):
        parts.append(Image(data=base64.b64decode(result["image"]), format="png"))
    return parts


@mcp.tool()
def click(pid: int | None = None, window_id: int | None = None, element_index: int | None = None, x: int | None = None, y: int | None = None, modifier: list[str] | None = None) -> dict[str, Any]:
    """Left-click an element index from get_window_state or an x/y coordinate."""
    return driver.click(pid=pid, window_id=window_id, element_index=element_index, x=x, y=y, modifier=modifier)


@mcp.tool()
def double_click(element_index: int | None = None, x: int | None = None, y: int | None = None, modifier: list[str] | None = None) -> dict[str, Any]:
    """Double-click an element or coordinate."""
    return driver.double_click(element_index=element_index, x=x, y=y, modifier=modifier)


@mcp.tool()
def right_click(element_index: int | None = None, x: int | None = None, y: int | None = None, modifier: list[str] | None = None) -> dict[str, Any]:
    """Right-click an element or coordinate."""
    return driver.right_click(element_index=element_index, x=x, y=y, modifier=modifier)


@mcp.tool()
def middle_click(element_index: int | None = None, x: int | None = None, y: int | None = None, modifier: list[str] | None = None) -> dict[str, Any]:
    """Middle-click an element or coordinate."""
    return driver.middle_click(element_index=element_index, x=x, y=y, modifier=modifier)


@mcp.tool()
def drag(from_element: int | None = None, to_element: int | None = None, from_x: int | None = None, from_y: int | None = None, to_x: int | None = None, to_y: int | None = None) -> dict[str, Any]:
    """Drag from one element/coordinate to another."""
    return driver.drag(from_element=from_element, to_element=to_element, from_x=from_x, from_y=from_y, to_x=to_x, to_y=to_y)


@mcp.tool()
def scroll(direction: str, amount: int = 3, element_index: int | None = None, x: int | None = None, y: int | None = None) -> dict[str, Any]:
    """Scroll at current pointer, element, or coordinate."""
    return driver.scroll(direction=direction, amount=amount, element_index=element_index, x=x, y=y)


@mcp.tool()
def type_text(pid: int | None = None, text: str = "") -> dict[str, Any]:
    """Type text into the focused app/window."""
    return driver.type_text(pid=pid, text=text)


@mcp.tool()
def press_key(pid: int | None = None, key: str = "") -> dict[str, Any]:
    """Press a single key."""
    return driver.press_key(key=key)


@mcp.tool()
def hotkey(pid: int | None = None, keys: list[str] | None = None) -> dict[str, Any]:
    """Press a key combination, e.g. ['ctrl', 'l']."""
    return driver.hotkey(keys=keys or [])


@mcp.tool()
def set_value(pid: int | None = None, window_id: int | None = None, element_index: int | None = None, value: str = "") -> dict[str, Any]:
    """Set an element value using the generic click/select/type fallback."""
    if element_index is None:
        return {"ok": False, "message": "element_index is required"}
    return driver.set_value(element_index=element_index, value=value)


@mcp.tool()
def focus_app(app: str, raise_window: bool = False) -> dict[str, Any]:
    """Target or raise an app by process/window title substring."""
    return driver.focus_app(app=app, raise_window=raise_window)


def run() -> None:
    mcp.run()
