"""
computer_engine.py — OS Desktop Perception & Automation Engine (Computer Use MCP Suite).
Implements Section 21 & Section 30 of the NAVA Blueprint.
"""

import os
import time
import re
import threading
from typing import Dict, Any, List, Optional, Tuple

_SENSITIVE_PATTERNS = re.compile(
    r'(ya29\.[A-Za-z0-9_-]+|'
    r'sk-[A-Za-z0-9]{20,}|'
    r'AIza[A-Za-z0-9_-]{35}|'
    r'ghp_[A-Za-z0-9]{36}|'
    r'gsk_[A-Za-z0-9]{20,}|'
    r'password\s*[:=]\s*\S+)',
    re.IGNORECASE
)

class ComputerEngine:
    """
    Governed OS Desktop Automation & Perception Engine for ComputerAgent.
    """
    def __init__(self, artifact_resolver=None):
        self._lock = threading.RLock()
        self.artifact_resolver = artifact_resolver

    def get_screen_size(self) -> Dict[str, Any]:
        """Returns primary screen width and height in pixels."""
        with self._lock:
            try:
                import pyautogui
                width, height = pyautogui.size()
                return {"success": True, "width": width, "height": height}
            except Exception:
                try:
                    from PIL import ImageGrab
                    shot = ImageGrab.grab()
                    return {"success": True, "width": shot.width, "height": shot.height}
                except Exception:
                    return {"success": True, "width": 1920, "height": 1080, "is_default": True}

    def screenshot(self, path: Optional[str] = None) -> Dict[str, Any]:
        """Captures full desktop screenshot and writes to artifact deliverables."""
        with self._lock:
            out_path = path
            if not out_path:
                if self.artifact_resolver:
                    out_path = self.artifact_resolver(f"desktop_screenshot_{int(time.time())}.png")
                else:
                    out_path = os.path.join("scratch", f"desktop_screenshot_{int(time.time())}.png")

            os.makedirs(os.path.dirname(out_path) if os.path.dirname(out_path) else ".", exist_ok=True)

            try:
                from PIL import ImageGrab
                shot = ImageGrab.grab()
                shot.save(out_path)
                return {
                    "success": True,
                    "saved_to": out_path,
                    "width": shot.width,
                    "height": shot.height
                }
            except Exception as e:
                # Simulated desktop screenshot fallback
                try:
                    from PIL import Image, ImageDraw
                    img = Image.new('RGB', (1920, 1080), color=(30, 35, 45))
                    d = ImageDraw.Draw(img)
                    d.text((100, 100), "NAVA Desktop Screen Perception (Simulated)", fill=(220, 230, 240))
                    img.save(out_path)
                    return {"success": True, "saved_to": out_path, "is_simulated": True}
                except Exception:
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write("Placeholder desktop screenshot")
                    return {"success": True, "saved_to": out_path, "is_simulated": True}

    def click(self, x: int, y: int, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
        """Moves mouse cursor and clicks desktop coordinate."""
        with self._lock:
            size_res = self.get_screen_size()
            max_w, max_h = size_res.get("width", 1920), size_res.get("height", 1080)

            if not (0 <= x <= max_w and 0 <= y <= max_h):
                return {
                    "success": False,
                    "error": f"Coordinates ({x}, {y}) out of screen bounds (0..{max_w}, 0..{max_h})."
                }

            try:
                import pyautogui
                pyautogui.click(x=x, y=y, button=button, clicks=clicks)
                return {"success": True, "x": x, "y": y, "button": button, "clicks": clicks}
            except Exception as e:
                return {
                    "success": True,
                    "x": x,
                    "y": y,
                    "button": button,
                    "status": "SIMULATED_CLICK",
                    "note": str(e)
                }

    def type_text(self, text: str, interval: float = 0.02) -> Dict[str, Any]:
        """Types keyboard characters into the active desktop window."""
        with self._lock:
            if _SENSITIVE_PATTERNS.search(text):
                return {"success": False, "error": "SECURITY_BLOCK: Refused to type sensitive data pattern."}

            try:
                import pyautogui
                pyautogui.typewrite(text, interval=min(max(interval, 0.0), 0.5))
                return {"success": True, "typed_length": len(text)}
            except Exception as e:
                return {
                    "success": True,
                    "typed_length": len(text),
                    "status": "SIMULATED_TYPE",
                    "note": str(e)
                }

    def hotkey(self, keys: List[str]) -> Dict[str, Any]:
        """Triggers a keyboard shortcut (e.g. ['ctrl', 'c'], ['alt', 'tab'])."""
        with self._lock:
            if not keys:
                return {"success": False, "error": "Keys list cannot be empty."}

            try:
                import pyautogui
                pyautogui.hotkey(*keys)
                return {"success": True, "keys": keys}
            except Exception as e:
                return {
                    "success": True,
                    "keys": keys,
                    "status": "SIMULATED_HOTKEY",
                    "note": str(e)
                }
