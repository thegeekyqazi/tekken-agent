#!/usr/bin/env python3
"""
Verify that our VirtualPad creates a /dev/input/js* device properly.
Run this to test if DuckStation can detect it as sdl-X.
"""
import os
import sys
import time
import glob

# Add the harness to path
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 70)
print("DuckStation Controller Test - Checking /dev/input/js* creation")
print("=" * 70)

print("\nStep 1: Check existing joystick devices")
js_before = glob.glob("/dev/input/js*")
print(f"  Existing: {js_before if js_before else 'None'}")

print("\nStep 2: Creating VirtualPad in DuckStation mode...")
try:
    from tekken_harness.controller import VirtualPad

    pad = VirtualPad(name="Tekken Agent Pad", p1_side="left", emulator="duckstation")
    print("  ✓ VirtualPad created")

    print("\nStep 3: Waiting for kernel to register device...")
    time.sleep(1)

    print("\nStep 4: Checking for new joystick devices")
    js_after = glob.glob("/dev/input/js*")
    print(f"  Current: {js_after if js_after else 'None'}")

    new_js = set(js_after) - set(js_before)
    if new_js:
        js_device = list(new_js)[0]
        js_num = js_device.split('js')[-1]
        print(f"\n  ✓ SUCCESS: New joystick device: {js_device}")
        print(f"  ✓ DuckStation should see this as: sdl-{js_num}")
        print(f"\n  Device permissions:")
        os.system(f"ls -la {js_device}")
    else:
        print("\n  ⚠ No new js* device detected")
        print("  Checking if device was created but not registered as joystick...")

    print("\nStep 5: Device details from /proc/bus/input/devices")
    os.system("cat /proc/bus/input/devices | grep -A 15 'Tekken Agent Pad' || echo 'Device not found'")

    print("\n" + "=" * 70)
    print("INSTRUCTIONS FOR DUCKSTATION:")
    print("=" * 70)
    if new_js:
        js_num = list(new_js)[0].split('js')[-1]
        print(f"\n1. This controller is: sdl-{js_num}")
        print(f"2. Open DuckStation -> Settings -> Controllers")
        print(f"3. Port 1 -> Controller Type: Digital Controller")
        print(f"4. Look for 'Tekken Agent Pad' or 'sdl-{js_num}' in the device list")
        print(f"5. Use Automatic Mapping or manually map:")
        print(f"   - D-Pad: Use Hat/POV")
        print(f"   - Buttons: Cross=Button 0, Circle=Button 1, Square=Button 2, Triangle=Button 3")
        print(f"6. Save and test in game")
    else:
        print("\nTROUBLESHOOTING:")
        print("The device was created but joydev didn't create js* node.")
        print("Possible fixes:")
        print("  1. sudo modprobe -r joydev && sudo modprobe joydev")
        print("  2. Check: ls -la /sys/class/input/*/device/name")
        print("  3. Verify user in 'input' group: groups $USER")

    print("\n\nController will stay active. Press Ctrl+C to stop...")
    print("(Open DuckStation now and configure the controller)")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping...")

    pad.close()
    print("Controller closed.")

except ImportError as e:
    print(f"\n  ✗ ERROR: Cannot import - {e}")
    print("  Make sure you're in the venv: source .venv/bin/activate")
except Exception as e:
    print(f"\n  ✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
