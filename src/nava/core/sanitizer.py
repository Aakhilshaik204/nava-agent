import re
from typing import Optional

# Common prompt injection patterns (Section 30)
_INJECTION_PATTERNS = [
    re.compile(r'ignore\s+all\s+previous\s+instructions', re.IGNORECASE),
    re.compile(r'disregard\s+all\s+previous\s+instructions', re.IGNORECASE),
    re.compile(r'override\s+system\s+prompt', re.IGNORECASE),
    re.compile(r'you\s+are\s+now\s+in\s+developer\s+mode', re.IGNORECASE),
    re.compile(r'system\s+override\s*:', re.IGNORECASE),
    re.compile(r'<!--\s*system_override\s*-->', re.IGNORECASE),
]

def sanitize_prompt_text(text: str) -> str:
    """
    Sanitizes raw text from external sources to neutralize common prompt injection vectors.
    """
    if not isinstance(text, str):
        text = str(text)

    cleaned = text
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub('[PROMPT_INJECTION_FILTERED]', cleaned)
    return cleaned


def wrap_untrusted_content(content: str, source: str = "external", trust_level: str = "UNVERIFIED") -> str:
    """
    Wraps external untrusted content in strict Section 30 boundary delimiters.
    Escapes internal closing tags to prevent delimiter escape vulnerabilities.
    """
    if not isinstance(content, str):
        content = str(content)

    sanitized = sanitize_prompt_text(content)
    
    # Escape internal closing tags
    escaped = sanitized.replace("</untrusted_content>", "&lt;/untrusted_content&gt;")
    
    return f'<untrusted_content source="{source}" trust_level="{trust_level}">\n{escaped}\n</untrusted_content>'
