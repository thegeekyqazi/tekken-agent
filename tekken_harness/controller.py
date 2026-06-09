"""
Virtual gamepad for RPCS3 via Linux uinput.

Creates a virtual evdev gamepad ("Tekken Agent Pad") that RPCS3's evdev pad
handler can bind to like any physical controller. All Tekken inputs are
expressed as PS-style buttons:

    1 (LP) -> Square      2 (RP) -> Triangle
    3 (LK) -> Cross       4 (RK) -> Circle

Directions go out on the d-pad hat axes (ABS_HAT0X / ABS_HAT0Y), which is
what Tekken reads by default.

Requires: /dev/uinput writable by the current user (see README).
"""

from __future__ import annotations

import time
from contextlib import contextmanager

from evdev import UInput, AbsInfo, ecodes as e

FRAME = 1.0 / 60.0  # one PS3 frame

# PS-face-button mapping using standard Linux gamepad codes.
# RPCS3 evdev handler maps these 1:1 when you configure the pad once in the GUI.
BUTTONS = {
    "square":   e.BTN_WEST,    # 1 / LP
    "triangle": e.BTN_NORTH,   # 2 / RP
    "cross":    e.BTN_SOUTH,   # 3 / LK
    "circle":   e.BTN_EAST,    # 4 / RK
    "l1":       e.BTN_TL,
    "r1":       e.BTN_TR,
    "l2":       e.BTN_TL2,
    "r2":       e.BTN_TR2,
    "select":   e.BTN_SELECT,
    "start":    e.BTN_START,
    "l3":       e.BTN_THUMBL,
    "r3":       e.BTN_THUMBR,
}

# Tekken numeric notation -> button name
TEKKEN_BUTTONS = {
    "1": "square",
    "2": "triangle",
    "3": "cross",
    "4": "circle",
}

# Direction -> (hat_x, hat_y). evdev hat: x=-1 left, +1 right; y=-1 up, +1 down.
DIRECTIONS = {
    "n":  (0, 0),    # neutral
    "u":  (0, -1),
    "d":  (0, 1),
    "f":  (1, 0),    # assumes agent is Player 1 on the left side
    "b":  (-1, 0),
    "uf": (1, -1),
    "ub": (-1, -1),
    "df": (1, 1),
    "db": (-1, 1),
}


class VirtualPad:
    def __init__(self, name: str = "Tekken Agent Pad", p1_side: str = "left"):
        """p1_side: 'left' means f=right on screen. Flip if the agent is on the right."""
        self.flip = p1_side == "right"
        cap = {
            e.EV_KEY: list(BUTTONS.values()),
            e.EV_ABS: [
                (e.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)),
                (e.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0)),
                (e.ABS_X, AbsInfo(128, 0, 255, 0, 15, 0)),
                (e.ABS_Y, AbsInfo(128, 0, 255, 0, 15, 0)),
                (e.ABS_RX, AbsInfo(128, 0, 255, 0, 15, 0)),
                (e.ABS_RY, AbsInfo(128, 0, 255, 0, 15, 0)),
            ],
        }
        self.ui = UInput(cap, name=name, vendor=0x054C, product=0x0268)
        # Give RPCS3/udev a moment to register the device on first creation.
        time.sleep(0.5)
        self.neutral()

    # ---------- low level ----------

    def _syn(self):
        self.ui.syn()

    def set_direction(self, d: str):
        x, y = DIRECTIONS[d]
        if self.flip:
            x = -x
        self.ui.write(e.EV_ABS, e.ABS_HAT0X, x)
        self.ui.write(e.EV_ABS, e.ABS_HAT0Y, y)
        self._syn()

    def press(self, *names: str):
        for n in names:
            self.ui.write(e.EV_KEY, BUTTONS[n], 1)
        self._syn()

    def release(self, *names: str):
        for n in names:
            self.ui.write(e.EV_KEY, BUTTONS[n], 0)
        self._syn()

    def neutral(self):
        """Release everything."""
        for code in BUTTONS.values():
            self.ui.write(e.EV_KEY, code, 0)
        self.ui.write(e.EV_ABS, e.ABS_HAT0X, 0)
        self.ui.write(e.EV_ABS, e.ABS_HAT0Y, 0)
        self._syn()

    # ---------- timed primitives ----------

    def tap(self, names: list[str], frames: int = 3, direction: str = "n"):
        """Hold direction + buttons for `frames`, then release."""
        self.set_direction(direction)
        if names:
            self.press(*names)
        time.sleep(frames * FRAME)
        if names:
            self.release(*names)
        self.set_direction("n")

    def hold(self, frames: int, direction: str = "n", names: list[str] | None = None):
        self.set_direction(direction)
        if names:
            self.press(*names)
        time.sleep(frames * FRAME)
        if names:
            self.release(*names)
        self.set_direction("n")

    @contextmanager
    def held(self, direction: str = "n", names: list[str] | None = None):
        self.set_direction(direction)
        if names:
            self.press(*names)
        try:
            yield
        finally:
            if names:
                self.release(*names)
            self.set_direction("n")

    def close(self):
        self.neutral()
        self.ui.close()
