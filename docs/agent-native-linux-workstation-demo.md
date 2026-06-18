# Agent-Native Linux Workstation Demo

This demo packages `linux-computer-use` as more than an MCP server: it shows a Linux desktop acting as an AI operator's body.

## What it demonstrates

1. **See the desktop** — list visible X11 windows, capture a target window, and return a screenshot.
2. **Ground actions in UI state** — return a cua-compatible accessibility/SOM tree. If AT-SPI is sparse, fail over to a synthetic window element instead of returning nothing.
3. **Survive weird X11 windows** — if `import -window` fails, raise the window, capture the full screen, and crop using window geometry.
4. **Cover real apps** — GTK dialog, Chromium, terminal, and Drawing.
5. **Become a workstation loop** — pair desktop control with the Hermes machine cockpit, hotkey launcher, timeline snapshots, and Dreamer summaries.

## Prerequisites

Debian/Ubuntu/Mint packages:

```bash
sudo apt install xdotool wmctrl scrot imagemagick python3-gi gir1.2-atspi-2.0 zenity
```

Python dev install:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Run the demo

From the repo root:

```bash
python scripts/demo_agent_native_workstation.py
```

For focused checks:

```bash
linux-computer-use smoke
python scripts/live_coverage.py
```

Expected result:

- `linux-computer-use smoke` reports driver/window/capture checks passing.
- `scripts/live_coverage.py` reports `ok: true` for GTK dialog, Chromium, terminal, and Drawing.
- The machine cockpit prints a read-only workstation summary.

## Demo narrative

> This is the missing Linux body for autonomous agents. On macOS, high-quality desktop control depends on private/Apple-specific accessibility stacks. On Linux, we can compose the primitives directly: X11 window discovery, AT-SPI, screenshots, geometry, shell, cron, and Hermes skills. The result is an agent-native workstation: it can see apps, operate them, summarize machine state, wake from idle with timeline context, and expose a global hotkey launcher.

## Current caveats

- X11 actions can move the real pointer/focus.
- Wayland requires compositor-specific portals/backends for full control.
- Some apps expose sparse AT-SPI trees; the current fallback keeps the agent grounded at the window level rather than pretending controls exist.
- Full-screen crop fallback minimizes but does not eliminate occlusion risk.

## Public positioning

Headline:

> Agent-native Linux workstation: a local Linux desktop that AI agents can see, operate, and summarize.

Short version:

> `linux-computer-use` brings computer-use primitives to Linux through an MCP server: window discovery, screenshots, AT-SPI/SOM state, clicks, typing, scrolls, and safe fallbacks. Paired with Hermes, it becomes a local operator workstation with cockpit summaries, a global hotkey, and Dreamer timeline context.
