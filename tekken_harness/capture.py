"""
Capture the emulator game window as a JPEG for the vision model.

Supports: RPCS3 (PS3) and DuckStation (PS1)

Primary path (Hyprland): hyprctl clients to locate the emulator
window geometry, then grim to grab that region of the screen.

Fallback: full-screen grab (grim -o or scrot/maim on X11).

Returns (jpeg_bytes, media_type) ready to base64 into the API.
"""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import subprocess

from PIL import Image

MAX_WIDTH = int(os.environ.get("TEKKEN_AGENT_MAX_WIDTH", "1024"))
JPEG_QUALITY = int(os.environ.get("TEKKEN_AGENT_JPEG_QUALITY", "80"))
EMULATOR = os.environ.get("TEKKEN_EMULATOR", "rpcs3").lower()


def _hyprctl_json(*args: str):
    out = subprocess.run(
        ["hyprctl", *args, "-j"],
        capture_output=True, text=True, timeout=5, check=True,
    ).stdout
    return json.loads(out)


def _hyprland_emulator_geometry(emulator: str = "rpcs3") -> str | None:
    """Return 'x,y wxh' for a *visible* emulator window, or None.

    grim captures screen regions, not window contents — so an emulator window on
    another workspace (or hidden) would make us screenshot whatever is drawn
    at those coordinates instead (e.g. your editor). Only consider emulator
    windows that are mapped, not hidden, and on a currently-active workspace.

    Args:
        emulator: "rpcs3" (default) or "duckstation"
    """
    try:
        clients = _hyprctl_json("clients")
        monitors = _hyprctl_json("monitors")
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return None

    active_ws = {m["activeWorkspace"]["id"] for m in monitors}
    special_ws = {m["specialWorkspace"]["id"] for m in monitors if m.get("specialWorkspace", {}).get("id")}

    emulator_lower = emulator.lower()

    def is_target_emulator(c):
        cls = (c.get("class") or "").lower()
        initial_cls = (c.get("initialClass") or "").lower()
        title = (c.get("title") or "").lower()
        return (emulator_lower in cls
                or emulator_lower in initial_cls
                or emulator_lower in title)

    def is_visible(c):
        ws = c.get("workspace", {}).get("id")
        return (c.get("mapped", True)
                and not c.get("hidden", False)
                and (ws in active_ws or ws in special_ws))

    all_emulator = [c for c in clients if is_target_emulator(c)]
    visible = [c for c in all_emulator if is_visible(c)]

    if not visible:
        if all_emulator:
            ws_list = sorted({c.get("workspace", {}).get("name", "?") for c in all_emulator})
            print(f"[capture] WARNING: {emulator} window exists but is not visible "
                  f"(on workspace(s) {ws_list}). Switch to it / unhide it — "
                  f"falling back to full-screen grab.")
        return None

    # Prefer the biggest visible emulator window (the game render window, not GUI elements).
    best = max(visible, key=lambda c: c["size"][0] * c["size"][1])
    x, y = best["at"]
    w, h = best["size"]
    return f"{x},{y} {w}x{h}"


def capture_frame() -> tuple[bytes, str]:
    raw: bytes | None = None

    if shutil.which("grim"):
        geom = _hyprland_emulator_geometry(EMULATOR)
        cmd = ["grim", "-t", "png"]
        if geom:
            cmd += ["-g", geom]
        cmd += ["-"]
        try:
            raw = subprocess.run(cmd, capture_output=True, timeout=10, check=True).stdout
        except subprocess.SubprocessError:
            raw = None

    if raw is None and shutil.which("maim"):  # X11 fallback
        raw = subprocess.run(["maim"], capture_output=True, timeout=10, check=True).stdout

    if raw is None:
        raise RuntimeError(
            "No screenshot tool worked. Install grim (Wayland) or maim (X11)."
        )

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        img = img.resize((MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=JPEG_QUALITY)
    return buf.getvalue(), "image/jpeg"


def capture_b64() -> tuple[str, str]:
    data, media = capture_frame()
    return base64.b64encode(data).decode(), media
