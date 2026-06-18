#!/bin/bash
set -euo pipefail

# Live recording of GLM-5.2 running hermesbench with real agent
# Records the hermes-agent tmux sessions as they happen

SESSION="hb-live-record"
TRIGGER="/tmp/${SESSION}_go"
RUNNER_LOG="/tmp/${SESSION}_runner.log"
OUTPUT="videos/glm52_live_benchmark.mp4"
DISPLAY=":96"

cd ~/hermesbenchv0_1
GLM_KEY=$(grep '^GLM_API_KEY' ~/.hermes/.env | head -1 | cut -d'=' -f2-)
rm -f "$TRIGGER" "$RUNNER_LOG"
tmux kill-session -t "$SESSION" 2>/dev/null || true

mkdir -p videos

# ── Pane 1: Benchmark runner ──
tmux new-session -d -s "$SESSION" -x 200 -y 56 "printf '\033]2;Runner\033\\'; tput civis; echo '  ARMED — waiting for trigger'; while [ ! -f $TRIGGER ]; do sleep 0.2; done; clear; echo 'Starting GLM-5.2 benchmark with real agent...'; cd ~/hermesbenchv0_1 && env OPENAI_API_KEY=\"$GLM_KEY\" python3 -m hermesbench run --all --model glm-5.2 --base-url https://api.z.ai/api/coding/paas/v4 --real-agent 2>&1 | tee $RUNNER_LOG || true; echo ''; echo 'BENCHMARK COMPLETE'; sleep 10"

# ── Pane 2: Agent session (captures active hb-* tmux sessions) ──
tmux split-window -h -t "$SESSION":0 -l 45% "printf '\033]2;Agent Session\033\\'; tput civis; echo '  ARMED — waiting for agent sessions'; while [ ! -f $TRIGGER ]; do sleep 0.2; done; while true; do clear; S=\$(tmux list-sessions 2>/dev/null | grep 'hb-' | grep -v '$SESSION' | head -1 | cut -d: -f1); if [ -n \"\$S\" ]; then echo '=== Live Agent Session ==='; tmux capture-pane -t \"\$S\" -p -S -30; else echo '(waiting for next task...)'; fi; sleep 1; done"

# ── Pane 3: Scoreboard ──
tmux select-pane -t "$SESSION":0.0
tmux split-window -v -t "$SESSION":0.0 -l 40% "printf '\033]2;Scoreboard\033\\'; tput civis; echo '  ARMED'; while [ ! -f $TRIGGER ]; do sleep 0.2; done; while true; do clear; P=\$(grep -c PASS $RUNNER_LOG 2>/dev/null || echo 0); F=\$(grep -c FAIL $RUNNER_LOG 2>/dev/null || echo 0); echo '╔══════════════════════════╗'; echo \"║  PASS: \$P    FAIL: \$F     \"; echo '╚══════════════════════════╝'; tail -3 $RUNNER_LOG 2>/dev/null; sleep 2; done"

# Style
tmux select-layout -t "$SESSION":0 tiled
tmux set-option -t "$SESSION" pane-border-status top
tmux set-option -t "$SESSION" pane-border-format "#[bold,fg=cyan] #{pane_index}: #[fg=yellow]#{pane_title} "
tmux set-option -t "$SESSION" status-left "#[bold,fg=green] LIVE BENCHMARK "

echo "Session created. Starting recording..."

# ── Record via Xvfb + xterm + ffmpeg ──
Xvfb "$DISPLAY" -screen 0 1920x1080x24 -nocursor &
XVFB_PID=$!
sleep 3

xterm -display "$DISPLAY" -geometry 240x60+0+0 \
    -bg "#0a0a14" -fg "#e0e0e8" \
    -cr "#0a0a14" -ms "#0a0a14" \
    -xrm "XTerm*cursorBlink: false" \
    -fa "Monospace" -fs 10 \
    -e "tmux attach -t $SESSION" &
XTERM_PID=$!
sleep 5

# Fire trigger — benchmark starts
touch "$TRIGGER"

# Record for 120 seconds
echo "Recording 120s to $OUTPUT..."
ffmpeg -y -f x11grab -draw_mouse 0 \
    -video_size 1920x1080 -framerate 30 \
    -i "$DISPLAY" -t 120 \
    -c:v libx264 -preset fast -crf 18 -pix_fmt yuv420p \
    "$OUTPUT" 2>&1 | tail -3

# Cleanup
kill $XTERM_PID $XVFB_PID 2>/dev/null || true
tmux kill-session -t "$SESSION" 2>/dev/null || true

# Verify
ls -la "$OUTPUT"
ffprobe -v quiet -print_format json -show_format "$OUTPUT" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin)['format']; print(f'Duration: {float(d[\"duration\"]):.0f}s  Size: {int(d[\"size\"])/1e6:.1f} MB')"
