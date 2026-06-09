"""
Tekken notation parser + executor.

The agent emits standard Tekken notation strings and this module turns them
into frame-timed pad input. Supported grammar (case-insensitive):

  Single step:        "f", "df", "2", "df+2", "b+1+2", "uf+4"
  Sequence:           "f, f, 2"            (comma = consecutive steps)
  Hold a direction:   "hold b 30"          (frames)
  Dash / movement:    "ff" (dash), "bb" (backdash), "qcf", "qcb"
  Special tokens:     "ss_up" / "ss_down"  (sidestep)
                      "block_high" (hold b), "block_low" (hold db)
                      "throw_1" (1+3), "throw_2" (2+4)
  Menu tokens:        "menu_up/down/left/right", "confirm" (cross),
                      "back" (circle), "start", "select"

Examples the model can send:
  "f, f, 2"          running punch
  "df+2"             generic launcher attempt
  "d+1"              quick low check
  "uf+4"             hopkick
  "1, 2"             jab string
  "block_low"        crouch guard ~40 frames
"""

from __future__ import annotations

import time

from .controller import VirtualPad, TEKKEN_BUTTONS, DIRECTIONS, FRAME

DEFAULT_TAP_FRAMES = 4
STEP_GAP_FRAMES = 6  # gap between sequence steps so the game registers them separately

MACROS: dict[str, list[tuple[str, list[str], int]]] = {
    # name: list of (direction, buttons, frames)
    "ff":         [("f", [], 3), ("n", [], 2), ("f", [], 8)],
    "bb":         [("b", [], 3), ("n", [], 2), ("b", [], 8)],
    "qcf":        [("d", [], 2), ("df", [], 2), ("f", [], 2)],
    "qcb":        [("d", [], 2), ("db", [], 2), ("b", [], 2)],
    "ss_up":      [("u", [], 3), ("n", [], 2)],
    "ss_down":    [("d", [], 3), ("n", [], 2)],
    "block_high": [("b", [], 40)],
    "block_low":  [("db", [], 40)],
    "crouch":     [("d", [], 30)],
    "getup":      [("u", [], 4)],
    "throw_1":    [("n", ["square", "cross"], 4)],
    "throw_2":    [("n", ["triangle", "circle"], 4)],
    "rage":       [("d", ["square", "triangle"], 4)],  # placeholder; char-specific
    # menus
    "menu_up":    [("u", [], 3)],
    "menu_down":  [("d", [], 3)],
    "menu_left":  [("b", [], 3)],
    "menu_right": [("f", [], 3)],
    "confirm":    [("n", ["cross"], 4)],
    "back":       [("n", ["circle"], 4)],
    "start":      [("n", ["start"], 4)],
    "select":     [("n", ["select"], 4)],
}


def parse_step(step: str) -> tuple[str, list[str], int]:
    """Parse one step like 'df+2', 'b+1+2', 'f', or '2' -> (direction, buttons, frames)."""
    step = step.strip().lower()
    direction = "n"
    buttons: list[str] = []
    for part in step.split("+"):
        part = part.strip()
        if part in DIRECTIONS:
            direction = part
        elif part in TEKKEN_BUTTONS:
            buttons.append(TEKKEN_BUTTONS[part])
        else:
            raise ValueError(f"Unknown token: {part!r} in step {step!r}")
    return (direction, buttons, DEFAULT_TAP_FRAMES)


def parse_action(action: str) -> list[tuple[str, list[str], int]]:
    """Parse a full action string into a list of timed steps."""
    action = action.strip().lower()

    if action in MACROS:
        return MACROS[action]

    if action.startswith("hold "):
        # "hold b 30" or "hold db+1 20"
        parts = action.split()
        target = parts[1]
        frames = int(parts[2]) if len(parts) > 2 else 30
        d, btns, _ = parse_step(target)
        return [(d, btns, frames)]

    steps = []
    for raw in action.split(","):
        raw = raw.strip()
        if not raw:
            continue
        if raw in MACROS:
            steps.extend(MACROS[raw])
        else:
            steps.append(parse_step(raw))
    if not steps:
        raise ValueError(f"Empty action: {action!r}")
    return steps


def execute(pad: VirtualPad, action: str):
    """Execute one action string on the pad, frame-timed."""
    steps = parse_action(action)
    for i, (direction, buttons, frames) in enumerate(steps):
        pad.set_direction(direction)
        if buttons:
            pad.press(*buttons)
        time.sleep(frames * FRAME)
        if buttons:
            pad.release(*buttons)
        pad.set_direction("n")
        if i < len(steps) - 1:
            time.sleep(STEP_GAP_FRAMES * FRAME)


def execute_plan(pad: VirtualPad, actions: list[str]):
    for a in actions:
        execute(pad, a)
