"""
Virtual gamepad for RPCS3 or DuckStation via Linux uinput.

Creates a virtual evdev gamepad ("Tekken Agent Pad") that emulators can bind
to like any physical controller. All Tekken inputs are expressed as PS-style
buttons:

    1 (LP) -> Square      2 (RP) -> Triangle
    3 (LK) -> Cross       4 (RK) -> Circle

Directions go out on the d-pad hat axes (ABS_HAT0X / ABS_HAT0Y), which is
what Tekken reads by default.

RPCS3 mode: Uses PS3 DualShock 3 vendor/product IDs for evdev handler.
DuckStation mode: Uses Xbox 360 IDs + trigger axes for better SDL compatibility.

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

# DuckStation reads the pad through SDL's GameController API, which identifies
# buttons by *index* (ascending evdev code order) and then applies its built-in
# Xbox 360 mapping (we fake an x360 GUID). Two consequences:
#   - The key set must match a real x360 pad EXACTLY. In particular BTN_TL2 /
#     BTN_TR2 must NOT exist as keys (real x360 triggers are axes only) — their
#     presence shifts every later button index, so Start lands on "LeftStick"
#     and Select on "Guide", i.e. Start/Select go dead in-game.
#   - SDL "X" (-> PS Square) is BTN_X == BTN_NORTH, and SDL "Y" (-> PS Triangle)
#     is BTN_Y == BTN_WEST, the opposite of the PS-style table above.
SDL_BUTTONS = {
    "square":   e.BTN_NORTH,   # SDL X  -> Square
    "triangle": e.BTN_WEST,    # SDL Y  -> Triangle
    "cross":    e.BTN_SOUTH,   # SDL A  -> Cross
    "circle":   e.BTN_EAST,    # SDL B  -> Circle
    "l1":       e.BTN_TL,
    "r1":       e.BTN_TR,
    "select":   e.BTN_SELECT,
    "start":    e.BTN_START,
    "l3":       e.BTN_THUMBL,
    "r3":       e.BTN_THUMBR,
}

# In SDL mode L2/R2 are analog trigger axes, not buttons.
SDL_TRIGGERS = {
    "l2": e.ABS_Z,
    "r2": e.ABS_RZ,
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
    def __init__(self, name: str = "Tekken Agent Pad", p1_side: str = "left", emulator: str = "rpcs3"):
        """
        Create a virtual gamepad compatible with RPCS3 or DuckStation.

        Args:
            name: Device name shown in system
            p1_side: 'left' means f=right on screen. Flip if the agent is on the right.
            emulator: 'rpcs3' (uses evdev directly) or 'duckstation' (SDL-compatible)
        """
        self.flip = p1_side == "right"
        self.emulator = emulator.lower()

        if self.emulator == "duckstation":
            # Mimic a real wired Xbox 360 pad (xpad driver) exactly, so SDL's
            # built-in mapping for the x360 GUID lines up index-for-index:
            # 11 buttons (no BTN_TL2/TR2!), sticks -32768..32767, triggers on
            # ABS_Z/RZ, d-pad on the hat.
            self.buttons = SDL_BUTTONS
            self.triggers = SDL_TRIGGERS
            self.stick_center = 0
            cap = {
                e.EV_KEY: list(SDL_BUTTONS.values()) + [e.BTN_MODE],
                e.EV_ABS: [
                    (e.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)),
                    (e.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0)),
                    (e.ABS_X, AbsInfo(0, -32768, 32767, 16, 128, 0)),
                    (e.ABS_Y, AbsInfo(0, -32768, 32767, 16, 128, 0)),
                    (e.ABS_RX, AbsInfo(0, -32768, 32767, 16, 128, 0)),
                    (e.ABS_RY, AbsInfo(0, -32768, 32767, 16, 128, 0)),
                    (e.ABS_Z, AbsInfo(0, 0, 255, 0, 0, 0)),   # L2 trigger
                    (e.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),  # R2 trigger
                ],
            }
            self.ui = UInput(cap, name=name, vendor=0x045E, product=0x028E,
                             version=0x0110, bustype=e.BUS_USB)
        else:
            # RPCS3 evdev handler: buttons are bound manually in the GUI, so
            # only consistency matters, not SDL's index conventions.
            self.buttons = BUTTONS
            self.triggers = {}
            self.stick_center = 128
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
            # PS3 DualShock 3 IDs
            self.ui = UInput(cap, name=name, vendor=0x054C, product=0x0268)

        # Give emulator/udev a moment to register the device on first creation.
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
            if n in self.triggers:  # analog trigger in SDL mode
                self.ui.write(e.EV_ABS, self.triggers[n], 255)
            else:
                self.ui.write(e.EV_KEY, self.buttons[n], 1)
        self._syn()

    def release(self, *names: str):
        for n in names:
            if n in self.triggers:
                self.ui.write(e.EV_ABS, self.triggers[n], 0)
            else:
                self.ui.write(e.EV_KEY, self.buttons[n], 0)
        self._syn()

    def neutral(self):
        """Release everything and center all axes."""
        for code in self.buttons.values():
            self.ui.write(e.EV_KEY, code, 0)
        self.ui.write(e.EV_ABS, e.ABS_HAT0X, 0)
        self.ui.write(e.EV_ABS, e.ABS_HAT0Y, 0)
        # Center analog sticks
        self.ui.write(e.EV_ABS, e.ABS_X, self.stick_center)
        self.ui.write(e.EV_ABS, e.ABS_Y, self.stick_center)
        self.ui.write(e.EV_ABS, e.ABS_RX, self.stick_center)
        self.ui.write(e.EV_ABS, e.ABS_RY, self.stick_center)
        # Reset triggers (SDL mode)
        for code in self.triggers.values():
            self.ui.write(e.EV_ABS, code, 0)
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
