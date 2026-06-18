# linux-computer-use — Product Hunt Submission Package

## Title
linux-computer-use: Desktop control for AI agents on Linux

## Tagline
Give AI agents eyes and hands on Linux — window discovery, screenshots, clicks, typing, and more via a lightweight MCP server.

## Description

### What is it?
linux-computer-use is an open-source MCP server that exposes a cua-driver-compatible tool surface for Linux desktops. It lets AI agents see and operate GUI applications through X11 — without macOS-only private APIs.

### Why build it?
AI agents can already answer questions. The next step is letting them operate your actual desktop: opening apps, clicking buttons, reading screens, typing text. On macOS, Apple's private accessibility stack makes this possible. On Linux, we had to compose the primitives ourselves.

### What does it do?

**See the desktop**
- List visible windows with geometry (xdotool + wmctrl fallback)
- Capture screenshots of specific windows or full screen
- Inspect UI structure through AT-SPI accessibility trees with SOM overlay

**Operate GUI apps**
- Click, double-click, right-click, middle-click by element index or coordinates
- Drag, scroll, type text, press keys, send hotkeys
- Focus/raise windows via xdotool or wmctrl

**Stay reliable**
- Stale element guards — fails closed instead of clicking on wrong window
- Window capture fallback — if `import -window` fails, crops from full-screen
- Smoke test CLI to verify driver health on Cinnamon/X11

**Become an agent workstation**
- Pairs with Hermes for cockpit summaries, hotkey launchers, and Dreamer context
- Machine health, repo state, vault priorities in one read-only command
- Timeline snapshots feed into between-session memory consolidation

### Try it

```bash
pip install linux-computer-use
linux-computer-use smoke
linux-computer-use mcp
```

Add to `~/.hermes/config.yaml`:
```yaml
mcp_servers:
  linux_computer_use:
    command: linux-computer-use
    args: ["mcp"]
```

### Compatibility
- Linux X11 (Cinnamon, MATE, GNOME, KDE)
- Requires: xdotool, wmctrl, scrot/import, python3-gi, gir1.2-atspi-2.0
- Wayland: detected, capture-only by default (compositor-specific portals needed for input)

### License
MIT

## Category
AI Agents — https://www.producthunt.com/categories/ai-agents

## Links
- GitHub: https://github.com/tyy130/linux-computer-use
- Demo video: [to be added after recording]

## Images to upload
1. `assets/full_desktop.png` — full desktop showing driver operating real apps
2. `assets/window_chrome_2097156.png` — Chromium window with SOM overlay
3. `assets/window_gnome-terminal-_88080390.png` — terminal showing smoke test output
4. `assets/live_coverage.json` — reference: 4/4 app classes passed coverage
5. GIF demo: to be recorded (see scripts/record_demo.sh)

## Topics / Tags
ai-agents, linux, desktop-automation, mcp, computer-use, x11, accessibility

## Maker comment (first comment, posted immediately after launch)

Hey hunters! 👋

I built linux-computer-use because I run my whole AI agent workflow on a Linux laptop and wanted agents to actually operate the desktop — not just answer questions about it.

The core idea: expose a cua-driver-compatible MCP tool surface for Linux X11, so Hermes/Claude/OpenAI agents can discover windows, capture screenshots, inspect UI trees, click/type/drag, and get reliable feedback when things go stale.

It's MIT licensed, works on Cinnamon out of the box, and pairs with the machine cockpit + hotkey launcher + Dreamer timeline loop I've been building for the agent-native Linux workstation.

Would love feedback, contributors, and ideas for Wayland/compositor backends!
