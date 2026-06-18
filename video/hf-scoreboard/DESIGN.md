# DESIGN.md — Hermes Agent Benchmark Scoreboard

## Style Prompt
Dark tech broadcast — competitive esports scoreboard meets terminal hacker aesthetic. Neon-lit, high contrast, kinetic energy. The viewer feels they're watching a live sporting event where an AI model is being tested in real-time.

## Colors

| Token | Hex | Role |
|---|---|---|
| `--bg-deep` | `#0A0C14` | Canvas background |
| `--bg-panel` | `#131620` | Scoreboard panel, cards |
| `--bg-terminal` | `#0D1117` | Terminal area background |
| `--border` | `#1E2330` | Subtle borders, dividers |
| `--pass` | `#00FF88` | PASS indicators, green checks, progress bar fill |
| `--fail` | `#FF3355` | FAIL indicators, red Xs, error states |
| `--accent` | `#00D4FF` | Model name, hyperlinks, tech labels |
| `--gold` | `#FFB800` | Counters, scores, highlight numbers |
| `--text-primary` | `#E8EAED` | Primary text |
| `--text-muted` | `#6B7280` | Secondary text, labels |

## Typography

| Family | Role | Weights |
|---|---|---|
| JetBrains Mono | Task IDs, terminal output, code snippets, counters | 400, 700 |
| Inter | Titles, labels, descriptions, scoreboard text | 400, 600, 700, 800 |

## Motion Character
- **Explosive entrances:** `back.out(1.7)` for scoreboard items, title slams
- **Smooth counters:** animated number tick-ups with `snap` plugin
- **Staggered reveals:** 0.05-0.08s stagger for list items
- **Shake on fail:** 2-3px x-axis shake for FAIL entries
- **Glow pulse:** `text-shadow` animate on PASS entries
- **Transitions:** `power2.inOut` crossfades between scenes

## What NOT to Do
- ❌ No gradient backgrounds — flat dark panels only
- ❌ No serif fonts anywhere
- ❌ No slow fades (>0.5s) on entrances — everything snaps
- ❌ No equalizer bars, waveform visualizers, or audio-reactive clichés
- ❌ No rounded corners > 4px — sharp, technical look
- ❌ No white backgrounds or light mode
- ❌ No Roboto font — JetBrains Mono + Inter only
