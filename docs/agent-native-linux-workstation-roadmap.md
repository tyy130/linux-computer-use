# Agent-Native Linux Workstation Roadmap

This repo is the wedge: make Linux a first-class body for AI operators, not a second-class fallback behind macOS computer-use tooling.

## North star

Turn a Cinnamon/X11 Linux laptop into a boringly reliable agent workstation:

- agents can see the desktop, windows, controls, and screenshots;
- agents can act through the safest available backend, not only coordinates;
- Hermes can summarize machine state and resume work after idle time;
- the system packages into a clear story: agent-native Linux workstation.

## Track 1 — Boring reliability on Cinnamon/X11

Definition of done:

- `linux-computer-use status` is green from normal terminals, Hermes MCP subprocesses, cron/gateway contexts, and login shells.
- Window discovery works through `xdotool` and has a `wmctrl` fallback.
- Window targeting is stable when multiple monitors and negative/offset geometries are present.
- `get_window_state` returns useful elements for GTK, Chromium/Electron, terminal, and common dialogs.
- Actions fail closed with clear messages when coordinates/elements are stale.
- A smoke-test command can open a known app, capture it, click/type, and verify the result.

Immediate hardening backlog:

1. Infer `DISPLAY`/`XAUTHORITY` when agents launch without desktop env.
2. Add `wmctrl -lpG` fallback for window listing and focus targeting.
3. Add stale-element/window-mismatch guard before element clicks.
4. Add active-window capture fallback when ImageMagick `import -window` fails.
5. Add live smoke tests that are opt-in and skipped in CI/headless mode.
6. Improve AT-SPI filtering so app windows return useful controls first and fail closed on stale elements.

## Track 2 — Machine cockpit skill

Definition of done:

A Hermes skill or command can produce a concise state report:

- OS/kernel/session type, uptime, CPU/RAM/swap pressure;
- disk pressure and top growth directories without unsafe deletion;
- running servers/listening ports;
- active GUI windows and browser state where available;
- workspace repos, dirty git state, recent commits, likely blockers;
- latest Obsidian daily note priorities and carry-forward items;
- latest Dreamer/timeline changes since last idle gap.

Suggested implementation:

- Start as a Hermes skill with a script under `scripts/machine_cockpit.py`.
- Keep it read-only by default.
- Emit both human summary and JSON for future cron/dreamer consumption.

## Track 3 — Linux AI launcher / global hotkey

Definition of done:

A global hotkey opens a lightweight prompt that routes to Hermes actions:

- quick ask: answer in-place;
- run skill: cockpit, repo audit, deploy check, browser task;
- operate UI: pass current window context to computer-use;
- capture context: screenshot/window title/clipboard included on demand.

Suggested path:

1. Prototype with Cinnamon custom keyboard shortcut -> shell script -> terminal prompt.
2. Upgrade to a tiny GTK/Qt launcher when the shell flow proves useful.
3. Add safe action templates before arbitrary commands.

## Track 4 — Timeline / Dreamer capture

Definition of done:

Hermes can say: “while you were gone, here’s what changed” with evidence.

Capture candidates:

- active window titles over time;
- shell command history deltas;
- git dirty-state/commit deltas in active repos;
- vault daily-note changes;
- cron job outputs and errors;
- optional screenshots or OCR summaries, with privacy controls.

Suggested path:

- Add a low-frequency read-only collector that writes JSONL snapshots.
- Have Dreamer consume snapshots during idle consolidation.
- Keep raw capture local; summarize only stable/relevant changes.

## Track 5 — Package the story

Definition of done:

This is no longer “an MCP server.” It is a product-shaped platform:

- README explains the agent-native Linux workstation vision.
- Demo script shows: inspect machine -> open app -> draw/type/click -> summarize state -> resume after idle.
- Install instructions cover Mint/Cinnamon first, then GNOME/KDE/Wayland caveats.
- Hermes integration path is one copy-paste config block plus doctor checks.
- Roadmap clearly separates reliable X11 now from compositor-specific Wayland later.

## Near-term execution order

1. Stabilize MCP environment detection and window discovery.
2. Add smoke-test harness and reliability checks.
3. Build machine cockpit as a read-only Hermes skill/script.
4. Wire a Cinnamon hotkey to Hermes cockpit/launcher prototype.
5. Extend Dreamer with read-only timeline snapshots.
6. Polish README/demo into the agent-native Linux workstation narrative.
