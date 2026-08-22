from playwright.sync_api import sync_playwright
import time
import json
import re

# Sensitive patterns that should never be typed into web forms
_SENSITIVE_PATTERNS = re.compile(
    r'(ya29\.[A-Za-z0-9_-]+|'          # Google OAuth tokens
    r'sk-[A-Za-z0-9]{20,}|'            # OpenAI API keys
    r'AIza[A-Za-z0-9_-]{35}|'          # Google API keys
    r'ghp_[A-Za-z0-9]{36}|'            # GitHub PATs
    r'gsk_[A-Za-z0-9]{20,}|'           # Groq API keys
    r'password\s*[:=]\s*\S+)',          # Passwords in key=value form
    re.IGNORECASE
)

# Blocked URL schemes and hosts
_BLOCKED_SCHEMES = ('file://', 'ftp://', 'javascript:', 'data:')
_BLOCKED_HOSTS = (
    'localhost', '127.0.0.1', '0.0.0.0',
    '169.254.',       # Link-local
    '10.',            # Private Class A
    '192.168.',       # Private Class C
)


def _is_url_blocked(url: str) -> bool:
    """Returns True if the URL targets a blocked scheme or private/local host."""
    lower = url.lower().strip()
    for scheme in _BLOCKED_SCHEMES:
        if lower.startswith(scheme):
            return True
    # Strip scheme to check host
    host_part = lower
    for prefix in ('https://', 'http://'):
        if host_part.startswith(prefix):
            host_part = host_part[len(prefix):]
            break
    host_part = host_part.split('/')[0].split(':')[0]  # Remove port and path
    for blocked in _BLOCKED_HOSTS:
        if host_part.startswith(blocked) or host_part == blocked.rstrip('.'):
            return True
    # Check 172.16.0.0/12 private range
    if host_part.startswith('172.'):
        try:
            second_octet = int(host_part.split('.')[1])
            if 16 <= second_octet <= 31:
                return True
        except (ValueError, IndexError):
            pass
    return False


def _escape_selector_for_js(selector: str) -> str:
    """Escape a CSS selector for safe interpolation into a JS string literal."""
    return selector.replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n')


import threading

class BrowserEngine:
    def __init__(self, headless=False):
        self._lock = threading.RLock()
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=headless)
        self.context = self.browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = self.context.new_page()

    # ── Navigation ────────────────────────────────────────────────────────

    def navigate(self, url: str) -> str:
        with self._lock:
            if not url:
                return "Error: url is required"
            if _is_url_blocked(url):
                return f"Error: URL blocked by security policy — {url}"
            try:
                self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                return f"Navigated to {url}"
            except Exception as e:
                return f"Navigation notice: {e}"

    def go_back(self) -> str:
        with self._lock:
            try:
                self.page.go_back(wait_until="domcontentloaded")
                time.sleep(1)
                return f"Went back to {self.page.url}"
            except Exception as e:
                return f"Go back error: {e}"

    def get_url(self) -> str:
        with self._lock:
            return self.page.url

    # ── Extraction ────────────────────────────────────────────────────────

    def extract_dom(self) -> str:
        """Returns raw page HTML (use extract_text for readable content)."""
        with self._lock:
            return self.page.content()

    def extract_text(self) -> str:
        """
        Extracts only the meaningful readable text from the page,
        stripping ads, navs, scripts, styles, and tracker noise.
        Returns clean text suitable for LLM consumption.
        """
        with self._lock:
            try:
                text = self.page.evaluate("""
                    () => {
                        // Remove noise elements before extracting text
                        const noiseSelectors = [
                            'script', 'style', 'noscript', 'iframe',
                            'nav', 'footer', 'header',
                            '.ad', '.ads', '.advertisement', '.advert',
                            '[role="banner"]', '[role="navigation"]', '[role="complementary"]',
                            '.sidebar', '.cookie-banner', '.popup', '.modal',
                            '[data-ad]', '[data-advertisement]',
                            '.social-share', '.share-buttons',
                            '.newsletter-signup', '.subscribe-box'
                        ];
                        noiseSelectors.forEach(sel => {
                            try {
                                document.querySelectorAll(sel).forEach(el => el.remove());
                            } catch(e) {}
                        });
                        
                        // Also remove hidden elements
                        document.querySelectorAll('[style*="display: none"], [style*="display:none"], [style*="visibility: hidden"], [style*="visibility:hidden"], [hidden]').forEach(el => el.remove());
                        
                        return document.body ? document.body.innerText : '';
                    }
                """)
            except Exception:
                text = ""
                
            raw_text = text.strip() if text else ""
            # Route through DOMSanitizer tripwire scanner and prompt injection filter (Section 30)
            try:
                from nava.governance.dom_sanitizer import DOMSanitizer
                from nava.core.sanitizer import sanitize_prompt_text
                sanitizer = DOMSanitizer()
                sanitizer.feed(f"<div>{raw_text}</div>")
                purified = "".join(sanitizer.purified_text)
                return sanitize_prompt_text(purified).strip()
            except Exception:
                return raw_text

    def screenshot(self, path: str = "scratch/screenshot.png") -> str:
        """Takes a screenshot of the current page."""
        with self._lock:
            import os
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            self.page.screenshot(path=path)
            return path

    # ── Interaction ───────────────────────────────────────────────────────

    def click(self, selector: str) -> str:
        with self._lock:
            safe_sel = _escape_selector_for_js(selector)
            # Visually highlight what we are about to click
            try:
                self.page.evaluate(f"""
                    (() => {{
                        const el = document.querySelector('{safe_sel}');
                        if (el) {{
                            el.style.outline = '3px solid red';
                            el.style.backgroundColor = 'rgba(255,0,0,0.15)';
                            el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }})()
                """)
                time.sleep(0.6)
            except:
                pass

            self.page.click(selector)
            time.sleep(2)
            return f"Clicked {selector}"

    def type_text(self, selector: str, text: str) -> str:
        with self._lock:
            # Security gate: refuse to type sensitive data
            if _SENSITIVE_PATTERNS.search(text):
                return "Error: SECURITY_BLOCK — refused to type text matching sensitive data patterns (API keys, tokens, passwords)."

            safe_sel = _escape_selector_for_js(selector)
            # Visually highlight
            try:
                self.page.evaluate(f"""
                    (() => {{
                        const el = document.querySelector('{safe_sel}');
                        if (el) {{
                            el.style.outline = '3px solid blue';
                            el.style.backgroundColor = 'rgba(0,0,255,0.15)';
                            el.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
                        }}
                    }})()
                """)
                time.sleep(0.5)
            except:
                pass

            self.page.fill(selector, text)
            time.sleep(1)
            return f"Typed '{text}' into {selector}"

    def scroll(self, pixels: int = 800) -> str:
        with self._lock:
            self.page.mouse.wheel(0, pixels)
            time.sleep(1)
            return f"Scrolled down by {pixels} pixels"

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def close(self):
        with self._lock:
            try:
                self.browser.close()
            except:
                pass
            try:
                self.playwright.stop()
            except:
                pass
