#!/usr/bin/env python3
"""
Debug script: Check if our virtual controller creates /dev/input/js* device
and verify SDL can detect it.
"""
import os
import time
import glob

print("Before creating controller:")
js_before = glob.glob("/dev/input/js*")
print(f"  Joystick devices: {js_before}")

print("\nCreating virtual controller...")
try:
    from evdev import UInput, AbsInfo, ecodes as e

    cap = {
        e.EV_KEY: [
            e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST,
            e.BTN_TL, e.BTN_TR, e.BTN_TL2, e.BTN_TR2,
            e.BTN_SELECT, e.BTN_START, e.BTN_THUMBL, e.BTN_THUMBR,
            e.BTN_MODE,
        ],
        e.EV_ABS: [
            (e.ABS_HAT0X, AbsInfo(0, -1, 1, 0, 0, 0)),
            (e.ABS_HAT0Y, AbsInfo(0, -1, 1, 0, 0, 0)),
            (e.ABS_X, AbsInfo(128, 0, 255, 0, 15, 0)),
            (e.ABS_Y, AbsInfo(128, 0, 255, 0, 15, 0)),
            (e.ABS_RX, AbsInfo(128, 0, 255, 0, 15, 0)),
            (e.ABS_RY, AbsInfo(128, 0, 255, 0, 15, 0)),
            (e.ABS_Z, AbsInfo(0, 0, 255, 0, 0, 0)),
            (e.ABS_RZ, AbsInfo(0, 0, 255, 0, 0, 0)),
        ],
    }

    ui = UInput(cap, name="Tekken Debug Pad", vendor=0x045E, product=0x028E,
                version=0x0110, bustype=e.BUS_USB)

    print("  Controller created, waiting for kernel to register...")
    time.sleep(1.5)

    js_after = glob.glob("/dev/input/js*")
    print(f"\nAfter creating controller:")
    print(f"  Joystick devices: {js_after}")

    new_js = set(js_after) - set(js_before)
    if new_js:
        print(f"\n✓ SUCCESS: New joystick device created: {new_js}")
        for js in new_js:
            print(f"\nDevice info for {js}:")
            os.system(f"ls -la {js}")
            print(f"\nSDL should detect this as: sdl-{js.split('js')[1]}")
    else:
        print("\n✗ PROBLEM: No /dev/input/js* device was created!")
        print("\nDebugging info:")
        os.system("cat /proc/bus/input/devices | grep -A 15 'Tekken Debug Pad'")
        print("\nPossible causes:")
        print("  1. joydev module not loaded: lsmod | grep joydev")
        print("  2. Insufficient capabilities for joystick detection")
        print("  3. udev rules blocking device creation")

    print("\nPress Ctrl+C to close the controller...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nClosing controller...")

    ui.close()
    print("Controller closed.")

except ImportError:
    print("ERROR: evdev module not installed")
    print("Run: pip install evdev")
except Exception as ex:
    print(f"ERROR: {ex}")
