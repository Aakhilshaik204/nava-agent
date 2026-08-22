import re
from html.parser import HTMLParser
from typing import Tuple, List

class DOMSanitizer(HTMLParser):
    def __init__(self, ledger=None):
        super().__init__()
        self.ledger = ledger
        self.purified_text = []
        self.ignored_depth = 0  # Depth counter instead of boolean flag
        self.ignored_tags = {'script', 'style', 'link', 'meta', 'noscript', 'iframe'}
        self.suspicion_flagged = False
        
        # Stack to track which tags opened an ignored region
        self._ignore_stack = []
        
        # Tripwire keywords
        self.dangerous_keywords = [
            "shell.execute",
            "file.delete",
            "mock.send_wire_transfer",
            "ignore previous instructions",
            "ignore all previous",
            "disregard prior",
            "system prompt",
            "you are now",
        ]

    def _scan_and_append(self, text: str):
        """Scans text for tripwires. Replaces matches with [SECURITY_BLOCK]."""
        lower_text = text.lower()
        has_tripwire = False
        
        for keyword in self.dangerous_keywords:
            if keyword in lower_text:
                has_tripwire = True
                break
                
        if has_tripwire:
            self.suspicion_flagged = True
            if self.ledger:
                from nava.core.schemas import Event
                import uuid
                evt = Event(
                    event_id=f"evt-{uuid.uuid4().hex[:8]}",
                    event_type="DOM_INJECTION_SUSPECTED",
                    task_id="browser",
                    payload={"matched_text": text[:100]}
                )
                self.ledger.append(evt.model_dump())
            self.purified_text.append("[SECURITY_BLOCK]")
        else:
            self.purified_text.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in self.ignored_tags:
            self.ignored_depth += 1
            self._ignore_stack.append(tag)
            return
        
        # If we're already inside an ignored region, stay ignored
        if self.ignored_depth > 0:
            return
            
        attr_dict = dict(attrs)
        
        # Structural Pruning: hidden inputs
        if tag == "input" and attr_dict.get("type", "").lower() == "hidden":
            self.ignored_depth += 1
            self._ignore_stack.append(tag)
            return
            
        # Structural Pruning: CSS hidden elements
        style = attr_dict.get("style", "").lower()
        if "display: none" in style or "display:none" in style or "visibility: hidden" in style or "visibility:hidden" in style:
            self.ignored_depth += 1
            self._ignore_stack.append(tag)
            return
        
        # Structural Pruning: zero-dimension iframes and elements
        width = attr_dict.get("width", "")
        height = attr_dict.get("height", "")
        if width == "0" and height == "0":
            self.ignored_depth += 1
            self._ignore_stack.append(tag)
            return
            
        # Scan Accessibility Attributes instead of stripping them
        for attr_name in ['alt', 'title', 'aria-label']:
            if attr_name in attr_dict and attr_dict[attr_name]:
                self._scan_and_append(f"[{attr_name}: {attr_dict[attr_name]}]")

    def handle_endtag(self, tag):
        # Only decrement if this tag actually opened an ignored region
        if self._ignore_stack and self._ignore_stack[-1] == tag:
            self._ignore_stack.pop()
            self.ignored_depth -= 1
        elif tag in self.ignored_tags and self.ignored_depth > 0:
            # Fallback: if we see a closing ignored tag but it wasn't on top of stack,
            # still try to decrement (handles malformed HTML gracefully)
            self.ignored_depth = max(0, self.ignored_depth - 1)
            if self._ignore_stack:
                # Remove the first matching tag from stack
                for i in range(len(self._ignore_stack) - 1, -1, -1):
                    if self._ignore_stack[i] == tag:
                        self._ignore_stack.pop(i)
                        break

    def handle_data(self, data):
        if self.ignored_depth == 0:
            stripped = data.strip()
            if stripped:
                self._scan_and_append(stripped)

def sanitize_dom(html_content: str, ledger=None) -> Tuple[str, bool]:
    """
    Returns (sanitized_text, is_suspicious)
    is_suspicious can be used to elevate risk for the agent's current session.
    """
    sanitizer = DOMSanitizer(ledger=ledger)
    sanitizer.feed(html_content)
    return " ".join(sanitizer.purified_text), sanitizer.suspicion_flagged
