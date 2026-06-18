# linux-computer-use

Linux desktop computer-use driver for AI agents.

This package exposes a small MCP server that mirrors the macOS `cua-driver mcp`
tool surface closely enough for agent backends to reuse the same workflow:

1. `get_window_state` captures a window, overlays numbered UI elements, and
   returns an accessibility tree.
2. The agent clicks, drags, scrolls, types, or sends keys by element index or
   coordinates.
3. `list_windows`, `list_apps`, `focus_app`, and `screenshot` provide the same
   discovery/capture primitives agents expect from computer-use systems.

## Current support

- Best path: Linux X11 sessions (`DISPLAY` set) with `xdotool`, `scrot`, and
  AT-SPI enabled.
- Works on Tyler's Cinnamon/X11 setup.
- Wayland is detected but not full-control by default. Most compositors block
  synthetic global input by design, so the package reports this limitation
  instead of pretending it can safely drive every app.

Important limitation versus macOS `cua-driver`: X11 cannot provide the exact
background co-working primitive Apple private APIs make possible. Actions may
move the real pointer and may require/steal focus. The MCP surface is designed
so Hermes can ship Linux support now and later swap in compositor-specific
backends for GNOME/KDE/Wayland.

## Install for development

```bash
cd linux-computer-use
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

System packages on Debian/Ubuntu/Mint:

```bash
sudo apt install xdotool scrot python3-gi gir1.2-atspi-2.0
```

## CLI

```bash
linux-computer-use status
linux-computer-use doctor --json
linux-computer-use mcp
```

## MCP tools

- `status`
- `list_windows`
- `list_apps`
- `screenshot`
- `get_window_state`
- `click`
- `double_click`
- `right_click`
- `drag`
- `scroll`
- `type_text`
- `press_key`
- `hotkey`
- `set_value`
- `focus_app`

## Hermes integration

Immediate path via Hermes native MCP client:

```yaml
mcp_servers:
  linux_computer_use:
    command: linux-computer-use
    args: ["mcp"]
```

Restart Hermes after adding that block to `~/.hermes/config.yaml`. Tools will
appear with names like `mcp_linux_computer_use_get_window_state` and
`mcp_linux_computer_use_click`.

Longer-term first-class path: Hermes can add a Linux backend for the existing
generic `computer_use` tool that starts:

```bash
linux-computer-use mcp
```

and maps the current single model-facing `computer_use` schema to the MCP tools
above. The model-facing schema does not need to change.

## Safety model

This driver intentionally does not implement its own LLM approval layer. It is
an execution backend. Agents embedding it should keep their own approval and
hard-block rules for destructive clicks/typing/keys, exactly like Hermes does
for the macOS computer-use tool.
