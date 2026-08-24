import os
import time
import re
import sys
import threading
from typing import Dict, Any, List, Optional, Tuple

# Sensitive patterns that should never be typed into OS inputs
_SENSITIVE_PATTERNS = re.compile(
    r'(ya29\.[A-Za-z0-9_-]+|'          # Google OAuth tokens
    r'sk-[A-Za-z0-9]{20,}|'            # OpenAI API keys
    r'AIza[A-Za-z0-9_-]{35}|'          # Google API keys
    r'ghp_[A-Za-z0-9]{36}|'            # GitHub PATs
    r'gsk_[A-Za-z0-9]{20,}|'           # Groq API keys
    r'password\s*[:=]\s*\S+)',         # Passwords in key=value form
    re.IGNORECASE
)

class DesktopEngine:
    """
    OS-Level Desktop GUI Automation Engine (Blueprint Section 21 & Claude Cowork Pillar A).
    Provides screen perception, DPI-scaling awareness, mouse movement/clicks/drags, and keyboard hotkeys.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self._pyautogui = None
        self._init_dpi_awareness()
        self._init_drivers()

    def _init_dpi_awareness(self):
        """Enable Per-Monitor DPI awareness on Windows to guarantee exact pixel coordinate clicks."""
        if sys.platform == "win32":
            try:
                import ctypes
                # Shcore.SetProcessDpiAwareness(2) -> Per-monitor DPI aware
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    import ctypes
                    ctypes.windll.user32.SetProcessDPIAware()
                except Exception:
                    pass

    def _init_drivers(self):
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
            pyautogui.PAUSE = 0.15
            self._pyautogui = pyautogui
        except ImportError:
            self._pyautogui = None

    def get_screen_size(self) -> Dict[str, Any]:
        """Returns the primary screen resolution and detected DPI scale."""
        with self._lock:
            dpi_scale = 1.0
            if sys.platform == "win32":
                try:
                    import ctypes
                    dpi = ctypes.windll.user32.GetDpiForSystem()
                    dpi_scale = round(dpi / 96.0, 2)
                except Exception:
                    dpi_scale = 1.0

            if self._pyautogui:
                size = self._pyautogui.size()
                return {"width": size.width, "height": size.height, "dpi_scale": dpi_scale}
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                return {"width": img.width, "height": img.height, "dpi_scale": dpi_scale}
            except Exception:
                return {"width": 1920, "height": 1080, "dpi_scale": dpi_scale}

    def screenshot(self, path: str = "artifacts/desktop_screenshot.png", region: Optional[Dict[str, int]] = None) -> str:
        """
        Takes a full or cropped region screenshot of the OS desktop.
        region: optional dict with keys {'left': int, 'top': int, 'width': int, 'height': int} or {'x1', 'y1', 'x2', 'y2'}
        """
        clean_p = path.replace("\\", "/")
        if "/" not in clean_p and not clean_p.startswith((".", "artifacts", "scratch")):
            path = os.path.join("artifacts", path)

        with self._lock:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            # Crop bbox tuple: (left, top, right, bottom)
            bbox = None
            if region:
                if "left" in region and "top" in region and "width" in region and "height" in region:
                    l = int(region["left"])
                    t = int(region["top"])
                    bbox = (l, t, l + int(region["width"]), t + int(region["height"]))
                elif "x1" in region and "y1" in region and "x2" in region and "y2" in region:
                    bbox = (int(region["x1"]), int(region["y1"]), int(region["x2"]), int(region["y2"]))

            try:
                from PIL import ImageGrab
                img = ImageGrab.grab(bbox=bbox)
                img.save(path)
                return path
            except Exception as e:
                if self._pyautogui:
                    # PyAutoGUI region is (left, top, width, height)
                    py_region = None
                    if bbox:
                        py_region = (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
                    self._pyautogui.screenshot(path, region=py_region)
                    return path
                raise RuntimeError(f"Screenshot capture failed: {e}")

    def click(self, x: int, y: int, button: str = "left", double: bool = False) -> str:
        """Moves cursor to (x, y) and performs a click or double click."""
        with self._lock:
            screen = self.get_screen_size()
            if x < 0 or x > screen["width"] or y < 0 or y > screen["height"]:
                return f"Error: Coordinates ({x}, {y}) out of screen bounds ({screen['width']}x{screen['height']})."

            if not self._pyautogui:
                return f"[Simulated Click] Clicked at ({x}, {y}) with button '{button}' (pyautogui not installed)."

            if double:
                self._pyautogui.doubleClick(x, y, button=button)
                return f"Double-clicked at ({x}, {y})"
            else:
                self._pyautogui.click(x, y, button=button)
                return f"Clicked at ({x}, {y}) with button '{button}'"

    def mouse_drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 0.5, button: str = "left") -> str:
        """Drags the mouse cursor from (start_x, start_y) to (end_x, end_y)."""
        with self._lock:
            screen = self.get_screen_size()
            for x, y in [(start_x, start_y), (end_x, end_y)]:
                if x < 0 or x > screen["width"] or y < 0 or y > screen["height"]:
                    return f"Error: Coordinates ({x}, {y}) out of screen bounds ({screen['width']}x{screen['height']})."

            if not self._pyautogui:
                return f"[Simulated Drag] Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})."

            self._pyautogui.moveTo(start_x, start_y)
            self._pyautogui.dragTo(end_x, end_y, duration=duration, button=button)
            return f"Dragged mouse from ({start_x}, {start_y}) to ({end_x}, {end_y})"

    def mouse_scroll(self, clicks: int = -3) -> str:
        """Scrolls the mouse wheel. Negative values scroll down, positive values scroll up."""
        with self._lock:
            if not self._pyautogui:
                return f"[Simulated Scroll] Scrolled mouse by {clicks} units."
            self._pyautogui.scroll(clicks)
            return f"Scrolled mouse by {clicks} units."

    def type_text(self, text: str) -> str:
        """Types text into the currently focused window."""
        with self._lock:
            if _SENSITIVE_PATTERNS.search(text):
                return "Error: SECURITY_BLOCK — refused to type text matching sensitive credential patterns."

            if not self._pyautogui:
                return f"[Simulated Type] Typed text length {len(text)} (pyautogui not installed)."

            self._pyautogui.typewrite(text, interval=0.02)
            return f"Successfully typed {len(text)} characters."

    def keyboard_press(self, key: str) -> str:
        """Presses a single key (e.g. 'enter', 'tab', 'esc', 'backspace', 'space', 'down')."""
        with self._lock:
            k = key.strip().lower()
            if not self._pyautogui:
                return f"[Simulated KeyPress] Pressed key '{k}'."
            self._pyautogui.press(k)
            return f"Pressed key '{k}'"

    def hotkey(self, keys: Any) -> str:
        """Presses a key combination (e.g. ['ctrl', 's'] or 'alt+tab')."""
        with self._lock:
            if isinstance(keys, str):
                key_list = [k.strip().lower() for k in keys.replace("+", " ").split()]
            elif isinstance(keys, list):
                key_list = [str(k).lower() for k in keys]
            else:
                return "Error: keys must be a list or string combination."

            if not self._pyautogui:
                return f"[Simulated Hotkey] Pressed {key_list}."

            self._pyautogui.hotkey(*key_list)
            return f"Pressed key combination: {'+'.join(key_list)}"
