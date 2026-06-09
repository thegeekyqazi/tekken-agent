"""Sanity check: creates the virtual pad and cycles through inputs for 15s.
Open RPCS3 -> Pads -> Handler: evdev, and 'Tekken Agent Pad' should appear.
You can also watch it with: evtest (pick the new device)."""
import time
from tekken_harness.controller import VirtualPad
from tekken_harness.moves import execute

pad = VirtualPad()
print("Pad created. Cycling test inputs for ~15s — bind it in RPCS3 now or watch evtest.")
for action in ["f", "b", "u", "d", "1", "2", "3", "4", "ff", "df+2", "1, 2", "block_low"]:
    print("  ->", action)
    execute(pad, action)
    time.sleep(0.5)
pad.close()
print("Done.")
