# DuckStation Controller Detection - Troubleshooting Guide

## Status: Controller IS Creating js0 ✓

Your virtual pad is correctly creating `/dev/input/js0`:
```
N: Name="Tekken Agent Pad"
I: Bus=0003 Vendor=045e Product=028e Version=0110
H: Handlers=event16 js0
```

DuckStation should detect this as **sdl-0** (the first SDL joystick).

## Testing Steps

### 1. Verify the controller is running:
```bash
# In terminal 1:
source .venv/bin/activate
TEKKEN_EMULATOR=duckstation python test_pad.py

# Leave this running!
```

### 2. Check DuckStation can see it:
```bash
# In terminal 2 (while test_pad.py is running):
ls -la /dev/input/js0
cat /sys/class/input/js0/device/name
# Should show: Tekken Agent Pad
```

### 3. Configure in DuckStation:

**While test_pad.py is running:**

1. Open DuckStation
2. **Settings** → **Controllers**
3. Port 1:
   - **Controller Type**: Digital Controller (or Analog Controller)
   - **Automatic Mapping** button
4. Look for **one of these**:
   - "Tekken Agent Pad"
   - "sdl-0" 
   - "SDL Controller"
   - "Xbox 360 Controller"
5. Select it and the buttons should auto-map
6. **Important**: Click **Save** button!
7. Close settings

### 4. Test in Tekken 3:
- Boot Tekken 3
- Go to main menu
- The d-pad should move the cursor
- Press Cross (button test in menu)

## If DuckStation Doesn't Detect It

### Check A: SDL can see the joystick
```bash
# Install sdl2-jstest if needed:
sudo dnf install sdl2-jstest

# While test_pad.py is running:
sdl2-jstest --list
# Should show: sdl-0 or similar

# Test the device:
sdl2-jstest --test 0
# You should see button/axis events
```

### Check B: DuckStation SDL backend
DuckStation might be using a specific SDL backend. Check:

1. **Settings** → **General** → **Log Level**: Set to "Debug"
2. Check the log window for SDL messages when you open controller settings
3. Look for lines like:
   - "Found X SDL controllers"
   - "Opening controller: sdl-0"

### Check C: Permissions
```bash
# Verify you're in the input group:
groups | grep input

# Check js0 permissions:
ls -la /dev/input/js0
# Should show: crw-rw-r--+ with group 'input'

# If not in group:
sudo usermod -aG input $USER
# Then log out and back in
```

### Check D: Controller order
If you have other controllers connected:
```bash
ls -la /dev/input/js*
# js0, js1, js2, etc.
```

DuckStation assigns:
- js0 = sdl-0
- js1 = sdl-1
- js2 = sdl-2

If Tekken Agent Pad is js0, use **sdl-0** in DuckStation.
If it's js1, use **sdl-1**, etc.

## Common Issues

### Issue 1: "Controller disconnected" in DuckStation
**Cause**: test_pad.py finished and closed the controller

**Fix**: Keep test_pad.py or the agent running continuously

### Issue 2: Wrong device selected
**Symptom**: DuckStation shows the controller but buttons don't work

**Fix**: 
1. Settings → Controllers → Port 1
2. Try selecting different devices in the list
3. Or manually map each button:
   - D-Pad Up: Hat 0 Up
   - D-Pad Down: Hat 0 Down
   - D-Pad Left: Hat 0 Left
   - D-Pad Right: Hat 0 Right
   - Cross: Button 0
   - Circle: Button 1
   - Square: Button 2
   - Triangle: Button 3
   - L1: Button 4
   - R1: Button 5
   - L2: Button 6
   - R2: Button 7
   - Select: Button 8
   - Start: Button 9

### Issue 3: Buttons mapped but reversed
**Cause**: DuckStation auto-map might use Xbox layout (A/B/X/Y) instead of PlayStation (Cross/Circle/Square/Triangle)

**Fix**: Manually swap button mappings:
- Cross should be Button 0 (not Button 1)
- Circle should be Button 1 (not Button 0)

### Issue 4: D-pad not working
**Symptom**: Buttons work but d-pad doesn't

**Fix**: Map d-pad to **Hat 0** (not Axis):
- Up: Hat 0 Up / Hat 0 Y-
- Down: Hat 0 Down / Hat 0 Y+
- Left: Hat 0 Left / Hat 0 X-
- Right: Hat 0 Right / Hat 0 X+

## Manual Button Mapping Reference

If automatic mapping fails, use this reference:

| PS Button | Linux Code | SDL Button # |
|-----------|------------|--------------|
| Cross | BTN_SOUTH | Button 0 |
| Circle | BTN_EAST | Button 1 |
| Square | BTN_WEST | Button 2 |
| Triangle | BTN_NORTH | Button 3 |
| L1 | BTN_TL | Button 4 |
| R1 | BTN_TR | Button 5 |
| L2 | BTN_TL2 | Button 6 |
| R2 | BTN_TR2 | Button 7 |
| Select | BTN_SELECT | Button 8 |
| Start | BTN_START | Button 9 |
| D-Pad | ABS_HAT0X/Y | Hat 0 |

## Running the Agent with DuckStation

Once controller is configured in DuckStation:

```bash
# In .env:
TEKKEN_EMULATOR=duckstation
TEKKEN_GAME=tekken3
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Run:
source .venv/bin/activate
python -m tekken_harness.agent

# The agent will keep the controller alive during gameplay
```

## Still Not Working?

1. **Check DuckStation version**: 
   ```bash
   duckstation --version
   ```
   Ensure you're running a recent version (2023+)

2. **Try different controller type**:
   - Digital Controller (simpler, Tekken 3 default)
   - Analog Controller (DualShock)
   - Try both

3. **Check DuckStation logs**:
   - Settings → Logging → Enable all
   - Check console/log file for SDL errors

4. **Test with another game**: 
   - Try a different PS1 game to verify the controller works
   - If other games work, it's Tekken 3-specific

5. **SDL version conflict**:
   ```bash
   ldd $(which duckstation) | grep SDL
   # Check which SDL version DuckStation is using
   ```

## Working Configuration Summary

When working correctly, you should see:
- ✓ `/dev/input/js0` exists with name "Tekken Agent Pad"
- ✓ DuckStation shows "sdl-0" or "Tekken Agent Pad" in controller list
- ✓ Automatic mapping or manual mapping completes without errors
- ✓ In-game menu cursor responds to d-pad
- ✓ Buttons trigger actions in game
