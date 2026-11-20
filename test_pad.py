"""Sanity check: creates the virtual pad and cycles through inputs for 15s.

For RPCS3: Open Pads -> Handler: evdev, and 'Tekken Agent Pad' should appear.
For DuckStation: Open Settings -> Controllers, 'Tekken Agent Pad' should appear.

You can also watch it with: evtest (pick the new device)
"""
import os
import sys
import time
from tekken_harness.controller import VirtualPad
from tekken_harness.moves import execute

emulator = os.environ.get("TEKKEN_EMULATOR", "rpcs3").lower()
print(f"Creating virtual pad for {emulator.upper()}...")
print("(Set TEKKEN_EMULATOR=duckstation for DuckStation mode)\n")

pad = VirtualPad(emulator=emulator)
print(f"Pad created. Cycling test inputs for ~15s — bind it in {emulator.upper()} now or watch evtest.\n")

for action in ["f", "b", "u", "d", "1", "2", "3", "4", "ff", "df+2", "1, 2", "block_low"]:
    print("  ->", action)
    execute(pad, action)
    time.sleep(0.5)

pad.close()
print("\nDone.")
