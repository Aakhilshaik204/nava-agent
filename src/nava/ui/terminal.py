import os
import re
import shutil
import time
from typing import List, Dict, Any, Optional, Tuple

class TerminalTheme:
    """
    State-of-the-Art ANSI 256 / True-Color Theme System for NAVA OS.
    Styled with modern Claude Code & Cursor terminal aesthetics.
    """
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    
    # Premium 256-Color Palette
    CORAL = "\033[38;5;209m"         # Claude Coral Accent
    BRIGHT_CORAL = "\033[38;5;215m"
    CYAN = "\033[38;5;45m"           # Primary Tech Cyan
    BRIGHT_CYAN = "\033[38;5;51m"
    EMERALD = "\033[38;5;48m"        # Success / Safe Green
    BRIGHT_EMERALD = "\033[38;5;84m"
    AMBER = "\033[38;5;214m"          # Warning / Running Yellow
    BRIGHT_AMBER = "\033[38;5;220m"
    CRIMSON = "\033[38;5;196m"        # Blocked / Risk Red
    VIOLET = "\033[38;5;141m"         # AI / Reviewer Purple
    SLATE = "\033[38;5;244m"          # Subtle Borders & Dim
    LIGHT_GRAY = "\033[38;5;250m"
    WHITE = "\033[38;5;255m"
    BG_DARK = "\033[48;5;235m"

    # Compatibility Color Aliases
    GREEN = EMERALD
    BRIGHT_GREEN = BRIGHT_EMERALD
    RED = CRIMSON
    BRIGHT_RED = CRIMSON
    YELLOW = AMBER
    BRIGHT_YELLOW = BRIGHT_AMBER
    BLUE = CYAN
    BRIGHT_BLUE = BRIGHT_CYAN
    MAGENTA = VIOLET
    BRIGHT_MAGENTA = VIOLET

    # Agent Role Badges
    ROLE_COLORS = {
        "CodingAgent": CYAN,
        "ResearchAgent": AMBER,
        "BrowserAgent": BRIGHT_CYAN,
        "ComputerAgent": VIOLET,
        "TerminalAgent": EMERALD,
        "ReviewerAgent": VIOLET,
        "DocumentAgent": CORAL,
        "DataAgent": BRIGHT_AMBER,
        "VerifierAgent": BRIGHT_EMERALD,
        "FileAgent": CYAN,
        "Orchestrator": BRIGHT_CORAL,
        "ActionGateway": CRIMSON,
        "TaskManager": EMERALD,
        "AITwin": VIOLET
    }

    ROLE_ICONS = {
        "CodingAgent": "💻",
        "ResearchAgent": "🔍",
        "BrowserAgent": "🌐",
        "ComputerAgent": "🖥️",
        "TerminalAgent": "⚡",
        "ReviewerAgent": "🛡️",
        "DocumentAgent": "📄",
        "DataAgent": "📊",
        "VerifierAgent": "✅",
        "FileAgent": "📁",
        "Orchestrator": "🧠",
        "ActionGateway": "🚪",
        "TaskManager": "📋",
        "AITwin": "👤"
    }

    @classmethod
    def badge(cls, role: str) -> str:
        color = cls.ROLE_COLORS.get(role, cls.CYAN)
        icon = cls.ROLE_ICONS.get(role, "🤖")
        return f"{color}{cls.BOLD}[{icon} {role}]{cls.RESET}"

    @classmethod
    def status_badge(cls, status: str) -> str:
        s = status.upper()
        if s in ["RUNNING", "SEARCHING", "COMPILING", "EXTRACTING", "OBSERVING"]:
            return f"{cls.AMBER}{cls.BOLD}● {s}{cls.RESET}"
        elif s in ["COMPLETED", "SUCCESS", "APPROVED", "OK", "VERIFIED"]:
            return f"{cls.EMERALD}{cls.BOLD}✔ {s}{cls.RESET}"
        elif s in ["FAILED", "ERROR", "BLOCKED", "EXHAUSTED", "KILLED"]:
            return f"{cls.CRIMSON}{cls.BOLD}✖ {s}{cls.RESET}"
        elif s in ["WAITING", "APPROVAL", "PAUSED", "WARNING"]:
            return f"{cls.AMBER}{cls.BOLD}⏳ {s}{cls.RESET}"
        return f"{cls.SLATE}[{status}]{cls.RESET}"


class BoxRenderer:
    """Renders modern Claude Code-style Unicode framed cards, banners, and diffs."""
    
    @staticmethod
    def get_width(max_w: int = 88) -> int:
        try:
            terminal_w = shutil.get_terminal_size().columns
            return min(max(terminal_w - 4, 60), max_w)
        except Exception:
            return max_w

    @classmethod
    def render_panel(
        cls,
        title: str,
        content_lines: List[str],
        color: str = TerminalTheme.CYAN,
        icon: str = "⚡",
        width: Optional[int] = None
    ) -> str:
        w = width or cls.get_width()
        inner_w = w - 4
        
        # Styled title with icon
        styled_title = f" {icon} {title} "
        title_len = len(cls._strip_ansi(styled_title))
        top_bar_len = max(inner_w - title_len - 2, 2)
        
        lines = []
        lines.append(f"{color}╭─{TerminalTheme.BOLD}{styled_title}{TerminalTheme.RESET}{color}{'─' * top_bar_len}╮{TerminalTheme.RESET}")
        
        for line in content_lines:
            clean_len = len(cls._strip_ansi(line))
            pad = max(inner_w - clean_len, 0)
            lines.append(f"{color}│{TerminalTheme.RESET} {line}{' ' * pad} {color}│{TerminalTheme.RESET}")
            
        lines.append(f"{color}╰{'─' * (inner_w + 2)}╯{TerminalTheme.RESET}")
        return "\n".join(lines)

    @classmethod
    def render_thinking(cls, agent_label: str, thought_text: str) -> str:
        """Renders an elegant collapsible-style reasoning card."""
        lines = [
            f"{TerminalTheme.DIM}{thought_text.strip()}{TerminalTheme.RESET}"
        ]
        return cls.render_panel(
            title=f"Thinking Process: {agent_label}",
            content_lines=lines,
            color=TerminalTheme.SLATE,
            icon="🧠"
        )

    @classmethod
    def render_tool_execution(cls, role: str, tool_name: str, args_summary: str, result_summary: str, is_success: bool = True) -> str:
        """Renders an action gateway execution receipt pill."""
        badge = TerminalTheme.badge(role)
        status_icon = f"{TerminalTheme.EMERALD}✔ SUCCESS{TerminalTheme.RESET}" if is_success else f"{TerminalTheme.CRIMSON}✖ FAILED{TerminalTheme.RESET}"
        
        lines = [
            f"{TerminalTheme.BOLD}Action:{TerminalTheme.RESET} {TerminalTheme.BRIGHT_CYAN}{tool_name}{TerminalTheme.RESET}({TerminalTheme.LIGHT_GRAY}{args_summary}{TerminalTheme.RESET})",
            f"{TerminalTheme.BOLD}Receipt:{TerminalTheme.RESET} {status_icon} • {TerminalTheme.DIM}{result_summary}{TerminalTheme.RESET}"
        ]
        return cls.render_panel(f"TOOL EXECUTION • {role}", lines, color=TerminalTheme.CYAN, icon="⚡")

    @classmethod
    def render_completion_card(
        cls,
        goal: str,
        task_id: str,
        duration_sec: float,
        artifacts: List[str],
        total_subtasks: int
    ) -> str:
        """Renders a polished Claude Code-style task completion card."""
        dur_str = f"{duration_sec:.1f}s"
        lines = [
            f"{TerminalTheme.BOLD}Goal:{TerminalTheme.RESET} {goal}",
            f"{TerminalTheme.BOLD}Status:{TerminalTheme.RESET} {TerminalTheme.EMERALD}{TerminalTheme.BOLD}● COMPLETED{TerminalTheme.RESET}  │  {TerminalTheme.BOLD}Time:{TerminalTheme.RESET} {dur_str}  │  {TerminalTheme.BOLD}Agents Dispatched:{TerminalTheme.RESET} {total_subtasks}",
            f"{TerminalTheme.BOLD}Audit Ledger:{TerminalTheme.RESET} {TerminalTheme.DIM}tasks/{task_id}/task_memory.md{TerminalTheme.RESET}"
        ]
        if artifacts:
            lines.append(f"")
            lines.append(f"{TerminalTheme.BOLD}Generated Deliverables:{TerminalTheme.RESET}")
            for art in artifacts:
                lines.append(f"  {TerminalTheme.EMERALD}📄 {art}{TerminalTheme.RESET}")
                
        return cls.render_panel("TASK COMPLETED SUCCESSFULLY", lines, color=TerminalTheme.EMERALD, icon="🎉")

    @classmethod
    def render_table(cls, headers: List[str], rows: List[List[str]], color: str = TerminalTheme.CYAN) -> str:
        if not rows:
            return f"{TerminalTheme.SLATE}(No records){TerminalTheme.RESET}"
            
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    clean_len = len(cls._strip_ansi(str(cell)))
                    col_widths[i] = max(col_widths[i], clean_len)

        lines = []
        header_cells = [f"{TerminalTheme.BOLD}{h.ljust(col_widths[i])}{TerminalTheme.RESET}" for i, h in enumerate(headers)]
        lines.append(f"{color} " + f" {TerminalTheme.SLATE}│{color} ".join(header_cells) + f"{TerminalTheme.RESET}")
        lines.append(f"{color}─" + f"─{TerminalTheme.SLATE}┼{color}─".join(['─' * w for w in col_widths]) + f"─{TerminalTheme.RESET}")
        
        for row in rows:
            row_cells = []
            for i, cell in enumerate(row):
                clean_len = len(cls._strip_ansi(str(cell)))
                pad = max(col_widths[i] - clean_len, 0)
                row_cells.append(f"{cell}{' ' * pad}")
            lines.append("  " + f" {TerminalTheme.SLATE}│{TerminalTheme.RESET} ".join(row_cells))
            
        return "\n".join(lines)

    @staticmethod
    def _strip_ansi(text: str) -> str:
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)


class AgentTreeVisualizer:
    """Renders real-time hierarchical stage and worker trees."""
    
    @classmethod
    def render_stage_header(cls, stage_num: int, total_stages: int, is_parallel: bool, worker_count: int) -> str:
        mode_tag = f"{TerminalTheme.EMERALD}⚡ PARALLEL ({worker_count} Workers){TerminalTheme.RESET}" if is_parallel else f"{TerminalTheme.CYAN}SEQUENTIAL{TerminalTheme.RESET}"
        return (
            f"\n{TerminalTheme.BOLD}{TerminalTheme.CYAN}╭─ Stage {stage_num}/{total_stages} Execution [{mode_tag}{TerminalTheme.CYAN}]{TerminalTheme.RESET}\n"
            f"{TerminalTheme.SLATE}│{TerminalTheme.RESET}"
        )

    @classmethod
    def render_worker_line(cls, worker_idx: int, is_last: bool, role: str, label: str, goal: str, status: str = "RUNNING") -> str:
        branch = "└─" if is_last else "├─"
        badge = TerminalTheme.badge(role)
        status_str = TerminalTheme.status_badge(status)
        return (
            f"{TerminalTheme.SLATE}│  {branch}{TerminalTheme.RESET} 🤖 {TerminalTheme.BOLD}Worker {worker_idx}:{TerminalTheme.RESET} {badge} {TerminalTheme.LIGHT_GRAY}({label}){TerminalTheme.RESET} → {status_str}\n"
            f"{TerminalTheme.SLATE}│     {TerminalTheme.DIM}Goal: {goal}{TerminalTheme.RESET}"
        )

    @classmethod
    def render_stage_footer(cls) -> str:
        return f"{TerminalTheme.SLATE}╰──────────────────────────────────────────────────────────────────────────{TerminalTheme.RESET}\n"
