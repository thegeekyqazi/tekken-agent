# Tekken 6 Agent Harness (RPCS3)

A see → think → act loop that lets a Claude vision model play Tekken 6 through RPCS3 on Linux. The harness creates a **virtual evdev gamepad** that RPCS3 treats as a real PS3 controller, screenshots the game window each cycle, asks the model for a short plan in Tekken notation, and executes it with frame-accurate timing.

```
┌──────────┐   grim (Hyprland)   ┌──────────────┐   JSON plan    ┌─────────────┐
│  RPCS3   │ ──── screenshot ──▶ │ Claude (API) │ ─────────────▶ │ moves.py    │
│ Tekken 6 │                     └──────────────┘  ["df+2","1,2"]│ frame timing│
│          │ ◀──── /dev/uinput virtual gamepad ◀──────────────── └─────────────┘
└──────────┘
```

## Why plans instead of per-frame input

An API round-trip is 1–3 s; Tekken runs at 60 fps. So the model doesn't press buttons directly — it emits 1–3 notation actions (`"df+2"`, `"f, f, 2"`, `"block_low"`) and the harness executes them with proper frame timing, then guards (`hold b`) while the next frame is being analyzed. It won't out-react a human, but it can play coherent neutral, navigate menus, and win rounds against the CPU on lower difficulties.

## Setup (Fedora / Hyprland)

### 1. Dependencies

```bash
sudo dnf install grim python3-devel   # grim is likely already on Hyprland
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

Copy the example environment file and configure your API keys:

```bash
cp .env.example .env
# Edit .env and set your ANTHROPIC_API_KEY or configure an alternative backend
```

The `.env.example` file includes:
- Anthropic API configuration (default backend)
- OpenAI-compatible backend options (OpenRouter, Ollama, LM Studio, vLLM)
- Optional agent behavior overrides (cycle count, screenshot size, etc.)

### 3. uinput permissions (one-time)

The virtual pad needs write access to `/dev/uinput`:

```bash
sudo modprobe uinput
echo 'KERNEL=="uinput", MODE="0660", GROUP="input", OPTIONS+="static_node=uinput"' \
  | sudo tee /etc/udev/rules.d/99-uinput.rules
sudo usermod -aG input $USER
sudo udevadm control --reload-rules && sudo udevadm trigger
# log out/in (or reboot) so the group change applies
echo uinput | sudo tee /etc/modules-load.d/uinput.conf   # load on boot
```

### 4. Bind the pad in RPCS3 (one-time)

```bash
python test_pad.py   # creates "Tekken Agent Pad" and cycles inputs for ~15s
```

While it's running, open RPCS3 → **Pads** → Player 1 → Handler: **evdev** → Device: **Tekken Agent Pad**. Map it like a standard pad (the test script's button cycle makes "press the button to bind" mapping easy — re-run it as needed). Save. Tekken defaults: Square=1 (LP), Triangle=2 (RP), Cross=3 (LK), Circle=4 (RK), d-pad for movement.

You can verify inputs independently with `evtest` (select the Tekken Agent Pad device).

### 5. Run

Boot Tekken 6 in RPCS3 (windowed or fullscreen — the capture module finds the RPCS3 window via `hyprctl` and crops to it), then:

```bash
python -m tekken_harness.agent                  # default: 200 cycles, P1 on left
python -m tekken_harness.agent --dry-run        # capture + model output, no inputs
python -m tekken_harness.agent --side right     # if your character is on the right
python -m tekken_harness.agent --cycles 50
```

The agent reports a mode each cycle (`menu` / `fight` / `loading`), so you can start it at the title screen and it will navigate into Arcade Battle by itself.

## Action language the model uses

| Kind | Examples |
|---|---|
| Single inputs | `f`, `df+2`, `b+1+2`, `uf+4` |
| Sequences | `1, 2` · `f, f, 2` · `d+1, df+2` |
| Holds | `hold b 30` · `hold db+1 20` |
| Movement macros | `ff` (dash), `bb` (backdash), `qcf`, `qcb`, `ss_up`, `ss_down` |
| Defense | `block_high`, `block_low`, `crouch`, `getup` |
| Throws | `throw_1` (1+3), `throw_2` (2+4) |
| Menus | `menu_up/down/left/right`, `confirm`, `back`, `start`, `select` |

Add character-specific combos by extending `MACROS` in `tekken_harness/moves.py` — e.g. give it Law's or Bryan's bread-and-butter strings as named macros and mention them in `SYSTEM_PROMPT` so the model can call them.

## Using other providers (OpenAI-compatible APIs)

The backend is pluggable via `.env` configuration — anything exposing an OpenAI-compatible `/v1/chat/completions` works (OpenRouter, Ollama, vLLM, LM Studio, llama.cpp server), as long as the model is **vision-capable**.

Edit your `.env` file and set:

```bash
TEKKEN_AGENT_BACKEND=openai
```

Then configure one of these options:

**OpenRouter**
```bash
OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=sk-or-xxxxx
TEKKEN_AGENT_MODEL=google/gemini-2.0-flash-001
```

**Ollama (local VLM)**
```bash
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_API_KEY=ollama
TEKKEN_AGENT_MODEL=qwen2.5-vl:7b
```

**LM Studio / vLLM / llama.cpp**  
See `.env.example` for additional provider templates.

The JSON parser strips code fences and extracts the first `{...}` block, covering most local models' formatting quirks — but small local VLMs read game HUDs less reliably than frontier models, so expect weaker play.

## Tuning knobs

- `TEKKEN_AGENT_MODEL` env var — vision model (defaults to Sonnet on Anthropic; Haiku is faster/cheaper for menu grinding, Opus thinks better in neutral).
- `MAX_WIDTH` in `capture.py` — image size sent to the model (smaller = faster cycles).
- `STEP_GAP_FRAMES` / `DEFAULT_TAP_FRAMES` in `moves.py` — if inputs drop or strings don't come out, nudge these.
- The post-plan guard (`pad.hold(15, direction="b")` in `agent.py`) — remove it for max aggression.

## Troubleshooting

- **Pad doesn't show in RPCS3:** check `groups` includes `input`; re-run `test_pad.py` while the Pads dialog is open (RPCS3 only lists currently-present devices).
- **Black/wrong screenshots:** if RPCS3 runs fullscreen on another monitor, grim grabs the window region reported by Hyprland — check `hyprctl clients | grep -i rpcs3`. Some Vulkan fullscreen modes don't composite; use borderless/windowed.
- **Inputs registering but moves whiffing:** raise `DEFAULT_TAP_FRAMES` to 5–6; RPCS3 input latency varies with frame pacing.
- **Sides swapped mid-match:** the model is told to check the left health bar; you can also restart with `--side right`.
