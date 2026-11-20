"""
Agent loop: see (screenshot) -> think (Claude vision) -> act (virtual pad).

Design notes
------------
LLM round-trips take 1-3s while Tekken runs at 60fps, so the agent doesn't
micro-input. Each cycle it returns a short PLAN of notation actions which the
harness executes with precise frame timing. Between plans the agent defaults
to guarding.

Two modes:
  menu  - navigating menus to get into a fight
  fight - in-round decision making
The model itself reports which mode it thinks it's in, so it can drive from
boot screen all the way into matches.

Supports: Tekken 6 (RPCS3) and Tekken 3 (DuckStation)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from collections import deque

from .capture import capture_b64
from .controller import VirtualPad
from .llm import LLM
from .moves import execute_plan, MACROS

GAME = os.environ.get("TEKKEN_GAME", "tekken6").lower()

SYSTEM_PROMPT_TEKKEN6 = f"""You are an agent playing Tekken 6 on a PS3 emulator (RPCS3). \
You see a screenshot of the game each turn and respond with controller actions.

You are PLAYER 1. Your character is normally on the LEFT side of the screen \
(sides can swap after wall splats — check the health bar: yours is the LEFT bar).

ACTION LANGUAGE (Tekken notation):
- Directions: f, b, u, d, df, db, uf, ub (f = toward opponent)
- Buttons: 1=left punch, 2=right punch, 3=left kick, 4=right kick
- Combine with '+': "df+2", "b+1+2". Sequence with commas: "f, f, 2" or "1, 2".
- "hold <dir> <frames>" e.g. "hold b 30"
- Macros: {", ".join(sorted(MACROS.keys()))}

RESPOND WITH ONLY a JSON object, no markdown fences:
{{
  "mode": "menu" | "fight" | "loading",
  "observation": "one sentence: what's on screen (health, range, opponent state)",
  "plan": ["action1", "action2", ...],
  "reasoning": "one sentence why"
}}

Rules of thumb in fights:
- At range: "ff" to close, or "df+2" / "f, f, 2" on approach.
- Up close: jab strings "1, 2", quick low "d+1", launcher attempt "df+2", hopkick "uf+4".
- If you just got hit or opponent is attacking: "block_high" or "block_low".
- If knocked down: "getup".
- Don't repeat the exact same plan more than twice in a row — mix highs/lows/throws.
- Keep plans short: 1-3 actions in fights (the screen changes fast), up to 5 in menus.
- mode "loading": empty plan, just wait.

In menus: use menu_up/menu_down/menu_left/menu_right, confirm, back, start. \
To reach a quick fight from the main menu, Arcade Battle or Practice are good targets. \
If a screen says "press start", send ["start"]."""

SYSTEM_PROMPT_TEKKEN3 = f"""You are an agent playing Tekken 3 on a PS1 emulator (DuckStation). \
You see a screenshot of the game each turn and respond with controller actions.

You are PLAYER 1. Your character is normally on the LEFT side of the screen \
(check the health bar: yours is the LEFT bar).

ACTION LANGUAGE (Tekken notation):
- Directions: f, b, u, d, df, db, uf, ub (f = toward opponent)
- Buttons: 1=left punch, 2=right punch, 3=left kick, 4=right kick
- Combine with '+': "df+2", "b+1+2". Sequence with commas: "f, f, 2" or "1, 2".
- "hold <dir> <frames>" e.g. "hold b 30"
- Macros: {", ".join(sorted(MACROS.keys()))}

RESPOND WITH ONLY a JSON object, no markdown fences:
{{
  "mode": "menu" | "fight" | "loading",
  "observation": "one sentence: what's on screen (health, range, opponent state)",
  "plan": ["action1", "action2", ...],
  "reasoning": "one sentence why"
}}

Rules of thumb in fights (Tekken 3 is faster and more aggressive than later games):
- At range: "ff" to close, or "df+2" on approach.
- Up close: jab strings "1, 2", quick low "d+3" or "d+4", launcher "df+2", hopkick "uf+4".
- If you just got hit or opponent is attacking: "block_high" or "block_low".
- If knocked down: "getup".
- Tekken 3 rewards aggression — stay close and pressure with strings.
- Don't repeat the exact same plan more than twice in a row — mix highs/lows/throws.
- Keep plans short: 1-3 actions in fights (the screen changes fast), up to 5 in menus.
- mode "loading": empty plan, just wait.

In menus: use menu_up/menu_down/menu_left/menu_right, confirm, back, start. \
To reach a quick fight from the main menu, Arcade or VS Mode are good targets. \
If a screen says "press start", send ["start"]."""

def get_system_prompt() -> str:
    """Return the appropriate system prompt based on TEKKEN_GAME env var."""
    if GAME == "tekken3":
        return SYSTEM_PROMPT_TEKKEN3
    return SYSTEM_PROMPT_TEKKEN6


def parse_response(text: str) -> dict:
    text = text.strip()
    # strip accidental code fences
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def run(max_cycles: int, p1_side: str, dry_run: bool, no_wait: bool = False):
    llm = LLM()  # backend/model from TEKKEN_AGENT_BACKEND / TEKKEN_AGENT_MODEL
    emulator = os.environ.get("TEKKEN_EMULATOR", "rpcs3").lower()
    pad = None if dry_run else VirtualPad(p1_side=p1_side, emulator=emulator)
    history: deque[str] = deque(maxlen=6)
    system_prompt = get_system_prompt()

    emulator_name = emulator.upper()
    game_name = GAME.upper()

    print(f"[harness] emulator={emulator_name} game={game_name} backend={llm.backend} model={llm.model} dry_run={dry_run}")
    if not dry_run:
        print(f"[harness] Virtual pad created and will stay alive for this whole session.")
        if not no_wait:
            print(
                f"\n  1. Launch {emulator_name} NOW (or open controller config if it's already running)\n"
                f"  2. Configure controller binding:\n"
                f"     RPCS3: Pads -> Player 1 -> Handler: Evdev -> Device: 'Tekken Agent Pad'\n"
                f"     DuckStation: Settings -> Controllers -> Port 1 -> Type: Digital Controller\n"
                f"                  Then map to 'Tekken Agent Pad' in controller settings\n"
                f"     It must NOT say '(disconnected)'. Save the configuration.\n"
                f"  3. Boot {game_name} and let the intro start playing.\n"
                f"     IMPORTANT: don't touch your keyboard/other controller in-game —\n"
                f"     whoever presses Start first gets claimed as P1.\n"
                f"  4. Press Enter below: the pad itself will press Start and then Cross\n"
                f"     (skip intro -> title screen -> menu), claiming P1, then\n"
                f"     tap d-pad up/down 3x as a sanity check.\n"
            )
            input(f"  Press Enter when {game_name}'s intro is playing... ")
            print("  Pressing Start to skip intro...")
            pad.tap(["start"], frames=6)
            time.sleep(4.0)  # wait for title screen to appear
            print("  Pressing Cross to proceed...")
            pad.tap(["cross"], frames=6)
            time.sleep(3.0)  # wait for main menu
            print("  Tapping d-pad up/down 3x — watch the menu cursor...")
            for _ in range(3):
                pad.hold(6, direction="d"); time.sleep(0.25)
                pad.hold(6, direction="u"); time.sleep(0.25)
            resp = input("  Did the menu cursor move up/down? [y/N] ").strip().lower()
            if resp != "y":
                print(f"  Binding not working — check {emulator_name} controller config and re-run.\n"
                      f"  If the cursor moved but you're unsure, 'y' is safe: the agent\n"
                      f"  re-checks the screen every cycle.")
                pad.close()
                return
            print("[harness] Binding confirmed, P1 claimed. Starting agent loop.\n")

    try:
        for cycle in range(max_cycles):
            t0 = time.time()
            img_b64, media = capture_b64()

            hist_text = "\n".join(history) if history else "(none yet)"
            raw = llm.complete(
                system=system_prompt,
                text=f"Cycle {cycle}. Your recent plans:\n{hist_text}\n\nCurrent frame attached. Respond with JSON only.",
                image_b64=img_b64,
                media_type=media,
            )

            try:
                decision = parse_response(raw)
            except Exception:
                print(f"[cycle {cycle}] unparseable response, blocking. Raw: {raw[:200]}")
                decision = {"mode": "fight", "plan": ["block_high"], "observation": "?", "reasoning": "parse failure fallback"}

            plan = decision.get("plan", [])
            print(f"[cycle {cycle}] mode={decision.get('mode')} | {decision.get('observation','')}")
            print(f"            plan={plan} | {decision.get('reasoning','')} | think={time.time()-t0:.1f}s")
            history.append(f"cycle {cycle}: {plan}")

            if dry_run or not plan:
                time.sleep(1.0)
                continue

            try:
                execute_plan(pad, plan)
            except ValueError as ex:
                print(f"            bad action skipped: {ex}")

            # brief guard between thinking cycles during fights
            if decision.get("mode") == "fight":
                pad.hold(15, direction="b")
    except KeyboardInterrupt:
        print("\n[harness] interrupted.")
    finally:
        if pad:
            pad.close()


def main():
    ap = argparse.ArgumentParser(description="LLM agent harness for Tekken (RPCS3 / DuckStation)")
    ap.add_argument("--cycles", type=int, default=200, help="max see-think-act cycles")
    ap.add_argument("--side", choices=["left", "right"], default="left",
                    help="which side P1 starts on (controls f/b orientation)")
    ap.add_argument("--dry-run", action="store_true",
                    help="capture + think but don't create a pad or send inputs")
    ap.add_argument("--no-wait", action="store_true",
                    help="skip the interactive setup/binding check at start")
    args = ap.parse_args()

    run(args.cycles, args.side, args.dry_run, args.no_wait)


if __name__ == "__main__":
    main()
