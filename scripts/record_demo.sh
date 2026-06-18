#!/usr/bin/env bash
# Record a demo GIF of linux-computer-use operating real apps.
# Requires: ffmpeg, xdotool, scrot
set -euo pipefail

DEMO_DIR="$(cd "$(dirname "$0")" && pwd)/assets"
mkdir -p "$DEMO_DIR/frames"
FRAMES="$DEMO_DIR/frames"

echo "=== linux-computer-use demo recording ==="
echo "This will take about 30 seconds."

# --- Frame 0: Clean desktop ---
echo "[1/6] Desktop baseline..."
sleep 1
scrot "$FRAMES/00_desktop.png"

# --- Frame 1: Open zenity dialog ---
echo "[2/6] Opening zenity dialog..."
zenity --info --title="Coverage Dialog" --text="linux-computer-use coverage dialog" --width=360 &
sleep 1
scrot "$FRAMES/01_dialog.png"

# --- Frame 2: Run smoke test in terminal ---
echo "[3/6] Running smoke test..."
WID=$(xdotool search --name "tdev | idle | running: hermes" 2>/dev/null | head -1)
if [ -z "$WID" ]; then
  xdotool search --name "Terminal" 2>/dev/null | head -1
fi
xdotool windowactivate "$WID" 2>/dev/null || true
sleep 0.3
xdotool type --window "$WID" --delay 30 "PYTHONPATH=src python3 -m linux_computer_use.cli smoke" 2>/dev/null || true
xdotool key --window "$WID" Return
sleep 4
scrot "$FRAMES/02_smoke_test.png"

# --- Frame 3: Run live coverage ---
echo "[4/6] Running live coverage..."
xdotool type --window "$WID" --delay 20 "python3 scripts/live_coverage.py" 2>/dev/null || true
xdotool key --window "$WID" Return
sleep 5
scrot "$FRAMES/03_coverage.png"

# --- Frame 4: Close dialog, show drawing ---
echo "[5/6] Drawing app..."
killall zenity 2>/dev/null || true
sleep 0.3
xdotool windowactivate "$(xdotool search --name "drawing" 2>/dev/null | head -1 || echo 0)" 2>/dev/null || true
sleep 0.5
scrot "$FRAMES/04_drawing.png"

# --- Frame 5: Final desktop ---
echo "[6/6] Final frame..."
sleep 0.5
scrot "$FRAMES/05_final.png"

# Compile GIF
echo "Compiling GIF..."
ffmpeg -y -framerate 2 -i "$FRAMES/%02d_desktop.png" \
  -vf "scale=1280:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" \
  -loop 0 "$DEMO_DIR/demo.gif" 2>/dev/null

echo "Demo GIF saved to: $DEMO_DIR/demo.gif"
echo "Frames saved in: $FRAMES"
ls -lh "$DEMO_DIR/demo.gif" 2>/dev/null || echo "GIF compile failed"
