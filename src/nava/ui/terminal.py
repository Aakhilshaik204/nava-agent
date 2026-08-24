import sys
import shutil
from typing import List, Dict, Any, Optional

class TerminalTheme:
    """ANSI 256 / true-color styling and role badge generator."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Core Colors
    CYAN = "\033[36m"
    BRIGHT_CYAN = "\033[96m"
    BLUE = "\033[34m"
    BRIGHT_BLUE = "\033[94m"
    GREEN = "\033[32m"
    BRIGHT_GREEN = "\033[92m"
    YELLOW = "\033[33m"
    BRIGHT_YELLOW = "\033[93m"
    RED = "\033[31m"
    BRIGHT_RED = "\033[91m"
    MAGENTA = "\033[35m"
    BRIGHT_MAGENTA = "\033[95m"
    GRAY = "\033[90m"
    WHITE = "\033[97m"

    # Agent Role Badges
    ROLE_COLORS = {
        "CodingAgent": BRIGHT_CYAN,
        "ResearchAgent": BRIGHT_YELLOW,
        "BrowserAgent": BRIGHT_BLUE,
        "ComputerAgent": BRIGHT_MAGENTA,
        "TerminalAgent": BRIGHT_GREEN,
        "ReviewerAgent": MAGENTA,
        "DocumentAgent": CYAN,
        "DataAgent": YELLOW,
        "VerifierAgent": GREEN,
        "FileAgent": BLUE,
        "Orchestrator": WHITE,
        "ActionGateway": RED,
        "TaskManager": BRIGHT_GREEN
    }

    @classmethod
    def badge(cls, role: str) -> str:
        color = cls.ROLE_COLORS.get(role, cls.CYAN)
        return f"{color}{cls.BOLD}[{role}]{cls.RESET}"

    @classmethod
    def status_badge(cls, status: str) -> str:
        status_upper = status.upper()
        if status_upper in ["RUNNING", "SEARCHING", "COMPILING", "EXTRACTING", "OBSERVING"]:
            return f"{cls.BRIGHT_YELLOW}{cls.BOLD}🔄 [{status_upper}]{cls.RESET}"
        elif status_upper in ["COMPLETED", "SUCCESS", "APPROVED", "OK", "VERIFIED"]:
            return f"{cls.BRIGHT_GREEN}{cls.BOLD}✅ [{status_upper}]{cls.RESET}"
        elif status_upper in ["FAILED", "ERROR", "BLOCKED", "EXHAUSTED", "KILLED"]:
            return f"{cls.BRIGHT_RED}{cls.BOLD}❌ [{status_upper}]{cls.RESET}"
        elif status_upper in ["WAITING", "APPROVAL", "PAUSED", "WARNING"]:
            return f"{cls.YELLOW}{cls.BOLD}⏳ [{status_upper}]{cls.RESET}"
        return f"{cls.CYAN}[{status}]{cls.RESET}"


class BoxRenderer:
    """Renders modern Unicode framed boxes, tables, and headers."""
    
    @staticmethod
    def get_width(max_w: int = 86) -> int:
        try:
            terminal_w = shutil.get_terminal_size().columns
            return min(max(terminal_w - 4, 60), max_w)
        except Exception:
            return max_w

    @classmethod
    def render_panel(cls, title: str, content_lines: List[str], color: str = TerminalTheme.CYAN, width: Optional[int] = None) -> str:
        w = width or cls.get_width()
        inner_w = w - 4
        
        # Clean title
        styled_title = f" {title} "
        title_len = len(title) + 2
        top_bar_len = max(inner_w - title_len - 2, 2)
        
        lines = []
        lines.append(f"{color}╭─{TerminalTheme.BOLD}{styled_title}{TerminalTheme.RESET}{color}{'─' * top_bar_len}╮{TerminalTheme.RESET}")
        
        for line in content_lines:
            # Simple line wrap or pad
            clean_len = len(cls._strip_ansi(line))
            pad = max(inner_w - clean_len, 0)
            lines.append(f"{color}│{TerminalTheme.RESET} {line}{' ' * pad} {color}│{TerminalTheme.RESET}")
            
        lines.append(f"{color}╰{'─' * (inner_w + 2)}╯{TerminalTheme.RESET}")
        return "\n".join(lines)

    @classmethod
    def render_table(cls, headers: List[str], rows: List[List[str]], color: str = TerminalTheme.CYAN) -> str:
        if not rows:
            return f"{TerminalTheme.GRAY}(No records){TerminalTheme.RESET}"
            
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    clean_len = len(cls._strip_ansi(str(cell)))
                    col_widths[i] = max(col_widths[i], clean_len)

        # Build table
        lines = []
        # Header row
        header_cells = [f"{TerminalTheme.BOLD}{h.ljust(col_widths[i])}{TerminalTheme.RESET}" for i, h in enumerate(headers)]
        lines.append(" │ ".join(header_cells))
        lines.append("─┼─".join(['─' * w for w in col_widths]))
        
        # Data rows
        for row in rows:
            row_cells = []
            for i, cell in enumerate(row):
                clean_len = len(cls._strip_ansi(str(cell)))
                pad = max(col_widths[i] - clean_len, 0)
                row_cells.append(f"{cell}{' ' * pad}")
            lines.append(" │ ".join(row_cells))
            
        return "\n".join(lines)

    @staticmethod
    def _strip_ansi(text: str) -> str:
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)


class AgentTreeVisualizer:
    """Renders real-time hierarchical stage and worker trees."""
    
    @classmethod
    def render_stage_header(cls, stage_num: int, total_stages: int, is_parallel: bool, worker_count: int) -> str:
        mode_tag = f"{TerminalTheme.BRIGHT_CYAN}PARALLEL ({worker_count} Workers){TerminalTheme.RESET}" if is_parallel else f"{TerminalTheme.WHITE}SEQUENTIAL{TerminalTheme.RESET}"
        return (
            f"\n{TerminalTheme.BOLD}╭─ Stage {stage_num}/{total_stages} Execution [{mode_tag}]{TerminalTheme.RESET}\n"
            f"{TerminalTheme.DIM}│{TerminalTheme.RESET}"
        )

    @classmethod
    def render_worker_line(cls, worker_idx: int, is_last: bool, role: str, label: str, goal: str, status: str = "RUNNING") -> str:
        branch = "└─" if is_last else "├─"
        badge = TerminalTheme.badge(role)
        status_str = TerminalTheme.status_badge(status)
        return f"{TerminalTheme.DIM}│  {branch}{TerminalTheme.RESET} 🤖 {TerminalTheme.BOLD}Worker {worker_idx}:{TerminalTheme.RESET} {badge} ({label}) → {status_str}\n{TerminalTheme.DIM}│     Goal: {goal}{TerminalTheme.RESET}"

    @classmethod
    def render_stage_footer(cls) -> str:
        return f"{TerminalTheme.DIM}╰──────────────────────────────────────────────────────────────────────────{TerminalTheme.RESET}\n"
