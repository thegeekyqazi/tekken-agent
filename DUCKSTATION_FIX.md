# DuckStation Controller Fix

## Problem
The virtual gamepad was being detected by DuckStation as "SDL PlayStation 3 Controller" but inputs weren't registering in-game.

## Root Cause
DuckStation uses SDL2 for controller input, which has different requirements than RPCS3's direct evdev handler:

1. **Vendor/Product IDs**: SDL expects common controller IDs it recognizes
2. **Trigger Axes**: SDL games often expect L2/R2 as analog axes (ABS_Z, ABS_RZ) in addition to buttons
3. **Device Capabilities**: SDL checks for specific capability combinations to identify controller types

## Solution
Added emulator-specific controller modes to `VirtualPad`:

### RPCS3 Mode (default)
- **Vendor**: 0x054C (Sony)
- **Product**: 0x0268 (PS3 DualShock 3)
- Uses evdev handler directly
- D-pad via HAT axes, face buttons via BTN_* codes

### DuckStation Mode
- **Vendor**: 0x045E (Microsoft)
- **Product**: 0x028E (Xbox 360 Controller)
- **Bus Type**: BUS_USB
- **Version**: 0x0110
- Mimics a real wired Xbox 360 pad (xpad driver) **exactly**: 11 buttons,
  sticks -32768..32767, L2/R2 as ABS_Z/ABS_RZ axes only, d-pad on the hat

**Why exact matching matters:** SDL identifies buttons by *index* (ascending
evdev code order) and applies its built-in Xbox 360 mapping for this GUID.
Earlier versions of the pad also declared BTN_TL2/BTN_TR2 as buttons — codes a
real x360 pad doesn't have — which shifted every later button index: Start
landed on SDL "LeftStick" and Select on "Guide", so Start/Select were dead
in-game. Additionally, SDL "X" (→ Square) is evdev BTN_X == BTN_NORTH and SDL
"Y" (→ Triangle) is BTN_Y == BTN_WEST, so DuckStation mode uses a different
square/triangle code mapping than RPCS3 mode (see `SDL_BUTTONS` in
`controller.py`) — otherwise left/right punch come out swapped.

## Usage

### For RPCS3 (default):
```bash
# In .env or shell:
TEKKEN_EMULATOR=rpcs3

# Test:
python test_pad.py
```

### For DuckStation:
```bash
# In .env:
TEKKEN_EMULATOR=duckstation

# Test:
TEKKEN_EMULATOR=duckstation python test_pad.py
```

The `test_pad.py` script now:
1. Reads `TEKKEN_EMULATOR` environment variable
2. Creates the appropriate virtual pad type
3. Cycles through test inputs for binding

## DuckStation Binding Steps

1. Start `test_pad.py` with DuckStation mode:
   ```bash
   TEKKEN_EMULATOR=duckstation python test_pad.py
   ```

2. Open DuckStation → **Settings** → **Controllers**

3. Port 1 → Controller Type: **Digital Controller** or **Analog Controller**

4. Click **Automatic Mapping**

5. Select **Tekken Agent Pad** from device list

6. Verify mappings (DuckStation shows SDL GameController names):
   - D-Pad: DPadUp/Down/Left/Right
   - Cross: A
   - Circle: B
   - Square: X
   - Triangle: Y
   - L1/R1: LeftShoulder/RightShoulder
   - L2/R2: LeftTrigger/RightTrigger

   Note: SDL may display the device as "Xbox 360 Controller" instead of
   "Tekken Agent Pad" — that's expected (the name comes from SDL's mapping
   database) and confirms the pad is being recognized correctly.

7. **Save** and close settings

8. Boot Tekken 3 and verify inputs work in-game

## Verification

Our virtual pad successfully creates a joystick device:
```bash
# Check the device:
cat /proc/bus/input/devices | grep -A 5 "Tekken Agent Pad"

# Expected output:
# N: Name="Tekken Agent Pad"
# I: Bus=0003 Vendor=045e Product=028e Version=0110
# H: Handlers=event16 js0
```

The device appears as **js0** which DuckStation detects as **sdl-0**.

Check the controller is working:
```bash
# While test_pad.py is running:
ls -la /dev/input/js0
cat /sys/class/input/js0/device/name  # Should show: Tekken Agent Pad

# Test with SDL:
sdl2-jstest --list    # Should show your controller
sdl2-jstest --test 0  # Should show button/axis events
```

## Technical Details

### Why Xbox 360 IDs?
- SDL2 has built-in mapping database (SDL_GameControllerDB)
- Xbox 360 controller (045e:028e) is one of the most recognized IDs
- Ensures SDL treats it as a standard gamepad without custom mapping
- DuckStation inherits SDL's controller detection logic

### Axis Centering
DuckStation/SDL expects analog axes to be centered at 128 (0-255 range):
- Left stick: ABS_X=128, ABS_Y=128
- Right stick: ABS_RX=128, ABS_RY=128
- Triggers: ABS_Z=0, ABS_RZ=0 (unpressed)

The `neutral()` method now centers all axes, not just the HAT.

### Backward Compatibility
✅ RPCS3 functionality unchanged - defaults to original behavior
✅ Existing setups continue working without modification
✅ Only DuckStation mode uses new IDs/capabilities
