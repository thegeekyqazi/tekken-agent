#!/usr/bin/env python3
"""
Test virtual controller for DuckStation compatibility.
Creates a controller with enhanced SDL compatibility.
"""
import time
from evdev import UInput, AbsInfo, ecodes as e

# Enhanced capabilities for DuckStation/SDL compatibility
def create_duckstation_pad():
    cap = {
        e.EV_KEY: [
            # Face buttons (standard gamepad)
            e.BTN_SOUTH,    # Cross/A
            e.BTN_EAST,     # Circle/B
            e.BTN_NORTH,    # Triangle/Y
            e.BTN_WEST,     # Square/X
            # Shoulder buttons
            e.BTN_TL,       # L1/LB
            e.BTN_TR,       # R1/RB
            e.BTN_TL2,      # L2/LT
            e.BTN_TR2,      # R2/RT
            # Menu buttons
            e.BTN_SELECT,
            e.BTN_START,
            # Thumbsticks
            e.BTN_THUMBL,
            e.BTN_THUMBR,
            # Mode button
            e.BTN_MODE,
        ],
        e.EV_ABS: [
            # D-pad via HAT
            (e.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)),
            (e.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0)),
            # Left analog stick
            (e.ABS_X, AbsInfo(128, 0, 255, 0, 15, 0)),
            (e.ABS_Y, AbsInfo(128, 0, 255, 0, 15, 0)),
            # Right analog stick
            (e.ABS_RX, AbsInfo(128, 0, 255, 0, 15, 0)),
            (e.ABS_RY, AbsInfo(128, 0, 255, 0, 15, 0)),
            # L2/R2 triggers as axes (some games expect this)
            (e.ABS_Z, AbsInfo(0, 0, 255, 0, 0, 0)),
            (e.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),
        ],
    }

    # Use generic vendor/product for better SDL compatibility
    ui = UInput(
        cap,
        name="Tekken Agent Pad",
        vendor=0x045E,  # Microsoft (generic gamepad)
        product=0x028E, # Xbox 360 controller (widely supported)
        version=0x0110,
        bustype=e.BUS_USB
    )

    # Neutral state
    ui.write(e.EV_ABS, e.ABS_HAT0X, 0)
    ui.write(e.EV_ABS, e.ABS_HAT0Y, 0)
    ui.write(e.EV_ABS, e.ABS_X, 128)
    ui.write(e.EV_ABS, e.ABS_Y, 128)
    ui.write(e.EV_ABS, e.ABS_RX, 128)
    ui.write(e.EV_ABS, e.ABS_RY, 128)
    ui.syn()

    return ui

print("Creating DuckStation-compatible virtual controller...")
pad = create_duckstation_pad()
time.sleep(1)

print("\nController created. Testing inputs for 20 seconds...")
print("Open DuckStation controller settings and try to map buttons now.")
print("\nTest sequence:")

tests = [
    ("D-pad UP", [(e.EV_ABS, e.ABS_HAT0Y, -1)]),
    ("D-pad DOWN", [(e.EV_ABS, e.ABS_HAT0Y, 1)]),
    ("D-pad LEFT", [(e.EV_ABS, e.ABS_HAT0X, -1)]),
    ("D-pad RIGHT", [(e.EV_ABS, e.ABS_HAT0X, 1)]),
    ("Cross/A", [(e.EV_KEY, e.BTN_SOUTH, 1)]),
    ("Circle/B", [(e.EV_KEY, e.BTN_EAST, 1)]),
    ("Square/X", [(e.EV_KEY, e.BTN_WEST, 1)]),
    ("Triangle/Y", [(e.EV_KEY, e.BTN_NORTH, 1)]),
    ("L1/LB", [(e.EV_KEY, e.BTN_TL, 1)]),
    ("R1/RB", [(e.EV_KEY, e.BTN_TR, 1)]),
    ("SELECT", [(e.EV_KEY, e.BTN_SELECT, 1)]),
    ("START", [(e.EV_KEY, e.BTN_START, 1)]),
]

for name, events in tests:
    print(f"  -> {name}")
    for ev_type, ev_code, value in events:
        pad.write(ev_type, ev_code, value)
    pad.syn()
    time.sleep(0.8)

    # Release
    for ev_type, ev_code, value in events:
        if ev_type == e.EV_KEY:
            pad.write(ev_type, ev_code, 0)
        elif ev_type == e.EV_ABS and ev_code in [e.ABS_HAT0X, e.ABS_HAT0Y]:
            pad.write(ev_type, ev_code, 0)
    pad.syn()
    time.sleep(0.3)

print("\nTest complete. Closing controller.")
pad.close()
