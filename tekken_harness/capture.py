"""
Capture the RPCS3 game window as a JPEG for the vision model.

Primary path (your setup): Hyprland -> hyprctl clients to locate the RPCS3
window geometry, then grim to grab that region of the screen.

Fallback: full-screen grab (grim -o or scrot/maim on X11).

Returns (jpeg_bytes, media_type) ready to base64 into the Anthropic API.
"""

from __future__ import annotations

import base64
import io
import json
import shutil
import subprocess

from PIL import Image

MAX_WIDTH = 1024  # downscale before sending to the model
JPEG_QUALITY = 80


def _hyprctl_json(*args: str):
    out = subprocess.run(
        ["hyprctl", *args, "-j"],
        capture_output=True, text=True, timeout=5, check=True,
    ).stdout
    return json.loads(out)


def _hyprland_rpcs3_geometry() -> str | None:
    """Return 'x,y wxh' for a *visible* RPCS3 window, or None.

    grim captures screen regions, not window contents — so an RPCS3 window on
    another workspace (or hidden) would make us screenshot whatever is drawn
    at those coordinates instead (e.g. your editor). Only consider rpcs3
    windows that are mapped, not hidden, and on a currently-active workspace.
    """
    try:
        clients = _hyprctl_json("clients")
        monitors = _hyprctl_json("monitors")
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return None

    active_ws = {m["activeWorkspace"]["id"] for m in monitors}
    special_ws = {m["specialWorkspace"]["id"] for m in monitors if m.get("specialWorkspace", {}).get("id")}

    def is_rpcs3(c):
        return ("rpcs3" in (c.get("class") or "").lower()
                or "rpcs3" in (c.get("initialClass") or "").lower())

    def is_visible(c):
        ws = c.get("workspace", {}).get("id")
        return (c.get("mapped", True)
                and not c.get("hidden", False)
                and (ws in active_ws or ws in special_ws))

    all_rpcs3 = [c for c in clients if is_rpcs3(c)]
    visible = [c for c in all_rpcs3 if is_visible(c)]

    if not visible:
        if all_rpcs3:
            ws_list = sorted({c.get("workspace", {}).get("name", "?") for c in all_rpcs3})
            print(f"[capture] WARNING: RPCS3 window exists but is not visible "
                  f"(on workspace(s) {ws_list}). Switch to it / unhide it — "
                  f"falling back to full-screen grab.")
        return None

    # Prefer the biggest visible rpcs3 window (the game render window, not the GUI log).
    best = max(visible, key=lambda c: c["size"][0] * c["size"][1])
    x, y = best["at"]
    w, h = best["size"]
    return f"{x},{y} {w}x{h}"


def capture_frame() -> tuple[bytes, str]:
    raw: bytes | None = None

    if shutil.which("grim"):
        geom = _hyprland_rpcs3_geometry()
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
