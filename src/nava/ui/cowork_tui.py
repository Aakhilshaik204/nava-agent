import os
import sys
import getpass
from typing import Optional, List, Dict, Any

from nava.orchestrator import Orchestrator
from nava.ui.terminal import TerminalTheme, BoxRenderer, AgentTreeVisualizer
from nava.core.message_bus import AgentMessage, MessageType
from nava.core.schemas import TaskBudget, BudgetStatus

class CoworkTUI:
    """
    Pillar D: Rich Cowork Interface (Section 33).
    Provides modern Claude Code / Cursor-style interactive terminal workspace,
    live agent trees, slash commands, and real-time governance visibility.
    """
    def __init__(self, orchestrator: Optional[Orchestrator] = None):
        self.orchestrator = orchestrator or Orchestrator()
        self._init_message_bus_listener()

    def _init_message_bus_listener(self):
        """Subscribes to global event bus for real-time progress rendering."""
        if hasattr(self.orchestrator, "message_bus") and self.orchestrator.message_bus:
            self.orchestrator.message_bus.add_global_listener(self._on_bus_message)

    def _on_bus_message(self, msg: AgentMessage):
        """Callback when agents or components broadcast on the message bus."""
        # Progress messages can be dynamically rendered if needed
        pass

    def print_banner(self):
        """Renders modern Claude Code-style NAVA Agentic OS banner."""
        proj_name = self.orchestrator.workspace.project_name if hasattr(self.orchestrator, "workspace") else "Nava"
        task_count = len(self.orchestrator.task_manager.list_tasks()) if hasattr(self.orchestrator, "task_manager") else 0
        all_skills = self.orchestrator.skill_manager.get_all_skills() if hasattr(self.orchestrator, "skill_manager") else {}
        total_skills = len(all_skills)
        
        banner_lines = [
            f"{TerminalTheme.BOLD}{TerminalTheme.BRIGHT_CORAL}NAVA AGENTIC OS{TerminalTheme.RESET} {TerminalTheme.SLATE}v0.2.0 • Personal Autonomous System{TerminalTheme.RESET}",
            f"{TerminalTheme.CYAN}Project:{TerminalTheme.RESET} {TerminalTheme.BOLD}{proj_name}{TerminalTheme.RESET}  │  {TerminalTheme.CYAN}Tasks:{TerminalTheme.RESET} {task_count}  │  {TerminalTheme.CYAN}Skills:{TerminalTheme.RESET} {total_skills}  │  {TerminalTheme.CYAN}Gateway:{TerminalTheme.RESET} {TerminalTheme.EMERALD}17-Step Enforced{TerminalTheme.RESET}",
            f"{TerminalTheme.DIM}Type your objective, or slash commands like {TerminalTheme.CYAN}/twin{TerminalTheme.RESET}{TerminalTheme.DIM}, {TerminalTheme.CYAN}/budget{TerminalTheme.RESET}{TerminalTheme.DIM}, {TerminalTheme.CYAN}/skills{TerminalTheme.RESET}{TerminalTheme.DIM}, {TerminalTheme.CYAN}/help{TerminalTheme.RESET}"
        ]
        print("\n" + BoxRenderer.render_panel("NAVA COWORK STUDIO", banner_lines, color=TerminalTheme.CORAL, icon="⚡"))

        # Welcome Back message if resuming workspace
        if hasattr(self.orchestrator, "workspace"):
            welcome = self.orchestrator.workspace.get_welcome_back_message()
            if welcome:
                print(f"\n{TerminalTheme.EMERALD}{welcome}{TerminalTheme.RESET}")

    def run(self):
        """Main interactive command loop."""
        self.print_banner()

        # Prompt for Gmail token if configured
        token = os.environ.get("GMAIL_API_TOKEN")
        if not token:
            print(f"\n{TerminalTheme.DIM}To enable Gmail MCP tools, enter a token (or press Enter to skip):{TerminalTheme.RESET}")
            try:
                token = getpass.getpass("Enter Gmail Access Token (ya29...): ").strip()
                if token:
                    os.environ["GMAIL_API_TOKEN"] = token
            except Exception:
                pass

        while True:
            try:
                proj = self.orchestrator.workspace.project_name if hasattr(self.orchestrator, "workspace") else "Nava"
                header_line = f"\n{TerminalTheme.SLATE}╭─{TerminalTheme.RESET} {TerminalTheme.BRIGHT_CORAL}⚡ Nava{TerminalTheme.RESET} {TerminalTheme.SLATE}@{TerminalTheme.RESET} {TerminalTheme.BOLD}{TerminalTheme.BRIGHT_CYAN}{proj}{TerminalTheme.RESET} {TerminalTheme.SLATE}[Active Workspace]{TerminalTheme.RESET}"
                prompt_str = f"{header_line}\n{TerminalTheme.SLATE}╰─{TerminalTheme.RESET}{TerminalTheme.BOLD}{TerminalTheme.BRIGHT_CORAL}❯{TerminalTheme.RESET} "
                user_input = input(prompt_str).strip()

                if not user_input:
                    continue

                if user_input.lower() in ["exit", "quit", "/exit", "/quit"]:
                    print(f"\n{TerminalTheme.CORAL}Shutting down Nava OS Shell. Goodbye! 👋{TerminalTheme.RESET}\n")
                    break

                # Dispatch command
                self.dispatch_command(user_input)

            except (KeyboardInterrupt, EOFError):
                print(f"\n\n{TerminalTheme.YELLOW}Session paused. Type 'exit' to quit or enter a new goal.{TerminalTheme.RESET}")
            except Exception as e:
                print(f"\n{TerminalTheme.BRIGHT_RED}[Fatal Error]{TerminalTheme.RESET} {e}")

    def dispatch_command(self, query: str):
        """Dispatches built-in slash commands or executes natural language goals."""
        lower_q = query.lower()

        # 1. Clean Task Session
        if lower_q in ["+ new", "new", "fresh", "/new"]:
            print(f"\n{TerminalTheme.BRIGHT_GREEN}✅ Started a brand new task session. Working memory is clean.{TerminalTheme.RESET}")
            return

        # 2. Emergency Kill Switch (/kill, /stop)
        if lower_q in ["/kill", "/stop", "kill", "stop"]:
            self._handle_kill_switch()
            return

        # 3. AI Twin Commands (/twin)
        if lower_q.startswith("/twin") or lower_q.startswith("twin"):
            self._handle_twin_command(query)
            return

        # 4. Budget & Governance Dashboard (/budget)
        if lower_q.startswith("/budget") or lower_q == "budget":
            self._handle_budget_command()
            return

        # 5. Skill Commands (/skills, /skill promote, /skill approve)
        if lower_q.startswith("/skill") or lower_q.startswith("skill"):
            self._handle_skill_command(query)
            return

        # 6. Project Management Commands (/projects, create project, switch project)
        if lower_q.startswith("create project ") or lower_q.startswith("project new ") or lower_q.startswith("/project create "):
            parts = query.split()
            pname = parts[2].strip() if len(parts) > 2 else "NewProject"
            self.orchestrator.workspace.create_project(pname)
            print(f"\n{TerminalTheme.BRIGHT_GREEN}✅ Created and switched to project: '{self.orchestrator.workspace.project_name}'{TerminalTheme.RESET}")
            print(f"{TerminalTheme.DIM}Memory initialized at: projects/{self.orchestrator.workspace.project_name}/project_memory.md{TerminalTheme.RESET}")
            return

        if lower_q.startswith("switch project ") or lower_q.startswith("project use ") or lower_q.startswith("/project switch "):
            parts = query.split()
            pname = parts[2].strip() if len(parts) > 2 else "Nava"
            self.orchestrator.workspace.switch_project(pname)
            print(f"\n{TerminalTheme.BRIGHT_CYAN}⇄ Switched active project to: '{self.orchestrator.workspace.project_name}'{TerminalTheme.RESET}")
            return

        if lower_q in ["projects", "/projects"]:
            self._handle_list_projects()
            return

        if lower_q in ["project", "/project"]:
            content = self.orchestrator.workspace.read_memory()
            print("\n" + BoxRenderer.render_panel("📌 CURRENT PROJECT MEMORY", content.splitlines(), color=TerminalTheme.CYAN))
            return

        # 7. Task History Commands (/tasks, /task <id>)
        if lower_q in ["tasks", "/tasks"]:
            self._handle_list_tasks()
            return

        if lower_q.startswith("task ") or lower_q.startswith("/task "):
            parts = query.split()
            if len(parts) > 1:
                tid = parts[1].strip()
                mem = self.orchestrator.task_manager.get_task_memory(tid)
                print("\n" + BoxRenderer.render_panel(f"📜 TASK AUDIT LEDGER: {tid}", mem.splitlines(), color=TerminalTheme.BLUE))
            else:
                print(f"{TerminalTheme.YELLOW}Usage: /task <task_id>{TerminalTheme.RESET}")
            return

        # 8. MCP Protocol Commands (/mcp, /mcp approve)
        if lower_q.startswith("/mcp") or lower_q == "mcp":
            self._handle_mcp_command(query)
            return

        # 9. Help Menu (/help, help, ?)
        if lower_q in ["help", "/help", "?"]:
            self._handle_help_menu()
            return

        # 10. Natural Language Goal Execution
        self._execute_goal_with_tree(query)

    def _handle_mcp_command(self, query: str):
        """Handles MCP server and tool schema inspection and approvals."""
        if query.strip() in ["/mcp", "mcp"]:
            pending = getattr(self.orchestrator.mcp_manager, "pending_tools", {})
            if not pending:
                print(f"\n{TerminalTheme.DIM}No external MCP servers currently active or discovered.{TerminalTheme.RESET}")
                return
            headers = ["Server Name", "Tool Name", "Trust Status", "Risk Level"]
            rows = []
            for s_name, tools in pending.items():
                for t_name, t_meta in tools.items():
                    trust = t_meta.get("trust_state", "UNTRUSTED_NEW")
                    risk = t_meta.get("risk_level", "MEDIUM")
                    status_badge = f"{TerminalTheme.BRIGHT_GREEN}✅ TRUSTED{TerminalTheme.RESET}" if trust == "TRUSTED" else f"{TerminalTheme.YELLOW}🆕 {trust}{TerminalTheme.RESET}"
                    rows.append([s_name, t_name, status_badge, risk])
            table_str = BoxRenderer.render_table(headers, rows)
            print("\n" + BoxRenderer.render_panel("🔌 MCP PROTOCOL TOOLS", table_str.splitlines(), color=TerminalTheme.MAGENTA))
            print(f"{TerminalTheme.DIM}Tip: Approve tools with '/mcp approve <server_name> <tool_name>'{TerminalTheme.RESET}")
            return
            
        # Delegate /mcp approve to orchestrator
        self.orchestrator.execute(query)

    def _handle_kill_switch(self):
        """Triggers immediate out-of-band emergency stop."""
        print(f"\n{TerminalTheme.BRIGHT_RED}{TerminalTheme.BOLD}🚨 TRIGGERING EMERGENCY KILL SWITCH...{TerminalTheme.RESET}")
        self.orchestrator.emergency_stop()
        print(f"{TerminalTheme.BRIGHT_RED}🛑 In-flight agents halted. Scoped credentials revoked. Concurrency locks released.{TerminalTheme.RESET}\n")

    def _handle_twin_command(self, query: str):
        """Displays or updates Tier 4 AI Twin persona and profile facts."""
        persona = self.orchestrator.ai_twin.get_persona()
        parts = query.split(maxsplit=3)

        if len(parts) >= 4 and parts[1].lower() == "set":
            key, val = parts[2].lower(), parts[3]
            valid_keys = ["name", "role", "preferred_communication_style", "working_hours", "timezone"]
            if key in valid_keys:
                self.orchestrator.ai_twin.update_persona({key: val}, explicit_user_action=True)
                print(f"\n{TerminalTheme.BRIGHT_GREEN}✅ AI Twin persona updated: {key} = '{val}'{TerminalTheme.RESET}")
            else:
                print(f"{TerminalTheme.YELLOW}Valid fields to update: {', '.join(valid_keys)}{TerminalTheme.RESET}")
            return

        # Render Persona Card
        persona_lines = [
            f"{TerminalTheme.BOLD}Name:{TerminalTheme.RESET} {persona.name}",
            f"{TerminalTheme.BOLD}Role:{TerminalTheme.RESET} {persona.role}",
            f"{TerminalTheme.BOLD}Communication Style:{TerminalTheme.RESET} {persona.preferred_communication_style}",
            f"{TerminalTheme.BOLD}Working Hours:{TerminalTheme.RESET} {persona.working_hours} ({persona.timezone})",
            f"{TerminalTheme.BOLD}Security Constraints:{TerminalTheme.RESET} {', '.join(persona.security_constraints)}",
            f"{TerminalTheme.BOLD}Authorized Tools:{TerminalTheme.RESET} {', '.join(persona.authorized_tool_preferences[:4])}...",
            f"",
            f"{TerminalTheme.DIM}Tip: Update fields with '/twin set <field> <value>' (e.g. '/twin set role Lead Architect'){TerminalTheme.RESET}"
        ]
        print("\n" + BoxRenderer.render_panel("👤 TIER 4 AI TWIN PROFILE", persona_lines, color=TerminalTheme.MAGENTA))

    def _handle_budget_command(self):
        """Displays resource budget metrics and runaway loop safety status."""
        active_budgets = getattr(self.orchestrator.budget_engine, "budgets", {})
        
        budget_lines = [
            f"{TerminalTheme.BOLD}Resource Budget Engine Status:{TerminalTheme.RESET} {TerminalTheme.BRIGHT_GREEN}ACTIVE{TerminalTheme.RESET}",
            f"{TerminalTheme.BOLD}Max Concurrent Agents:{TerminalTheme.RESET} 8",
            f"{TerminalTheme.BOLD}Max Spawn Depth:{TerminalTheme.RESET} 3",
            f"{TerminalTheme.BOLD}Runaway Loop Detector:{TerminalTheme.RESET} {TerminalTheme.BRIGHT_GREEN}SHA-256 State Hashing Active{TerminalTheme.RESET}",
            f""
        ]

        if not active_budgets:
            budget_lines.append(f"{TerminalTheme.DIM}No active task budget running. Limits apply automatically to all tasks.{TerminalTheme.RESET}")
        else:
            for tid, b in active_budgets.items():
                status_badge = TerminalTheme.status_badge(b.status.value if hasattr(b.status, "value") else str(b.status))
                budget_lines.append(f"Task {tid}: Steps {b.consumed_steps}/{b.max_steps} | Tokens {b.consumed_tokens}/{b.max_tokens} | Status {status_badge}")

        print("\n" + BoxRenderer.render_panel("📊 GOVERNANCE & RESOURCE BUDGET", budget_lines, color=TerminalTheme.YELLOW))

    def _handle_skill_command(self, query: str):
        """Handles skills listing, promotion, and approval."""
        parts = query.split(maxsplit=2)
        
        # /skill promote <name_or_goal>
        if len(parts) >= 2 and parts[1].lower() == "promote":
            skill_name = parts[2].strip() if len(parts) > 2 else "custom_workflow"
            tasks = self.orchestrator.task_manager.list_tasks()
            instructions = "Execute multi-step workflow adhering to NAVA safety constraints."
            if tasks:
                latest_task = tasks[-1]
                instructions = f"Replicate verified workflow from task '{latest_task['goal']}'."
                
            skill_def = self.orchestrator.skill_manager.promote_workflow_to_skill(
                skill_name=skill_name,
                description=f"Automated skill promoted from verified task workflow.",
                instructions=instructions,
                auto_approve=True
            )
            print(f"\n{TerminalTheme.BRIGHT_GREEN}✅ Successfully promoted workflow into permanent skill: '{skill_name}'{TerminalTheme.RESET}")
            print(f"{TerminalTheme.DIM}Saved to .nava/skills/{skill_name}/SKILL.md and approved in trusted plugins ledger.{TerminalTheme.RESET}")
            return

        # /skill approve <name | all>
        if len(parts) >= 2 and parts[1].lower() == "approve":
            target = parts[2].strip().lower() if len(parts) > 2 else "all"
            if target == "all":
                for s_name in self.orchestrator.skill_manager.get_all_skills():
                    self.orchestrator.skill_manager.approve_skill(s_name, approved_by="local_user")
                print(f"\n{TerminalTheme.BRIGHT_GREEN}✅ All registered skills have been hash-locked and approved.{TerminalTheme.RESET}")
            elif target in self.orchestrator.skill_manager.get_all_skills():
                self.orchestrator.skill_manager.approve_skill(target, approved_by="local_user")
                print(f"\n{TerminalTheme.BRIGHT_GREEN}✅ Skill '{target}' approved and hash-locked.{TerminalTheme.RESET}")
            else:
                print(f"\n{TerminalTheme.YELLOW}Skill '{target}' not found.{TerminalTheme.RESET}")
            return

        # List skills
        skills = self.orchestrator.skill_manager.get_all_skills()
        if not skills:
            print(f"\n{TerminalTheme.YELLOW}No skills registered in .nava/skills/ or ~/.nava/skills/{TerminalTheme.RESET}")
            return

        headers = ["Skill Name", "Status", "Description"]
        rows = []
        for name, s in skills.items():
            state_val = s.trust_state.value if hasattr(s.trust_state, "value") else str(s.trust_state)
            if state_val == "TRUSTED":
                status_str = f"{TerminalTheme.BRIGHT_GREEN}✅ TRUSTED{TerminalTheme.RESET}"
            elif state_val == "UNTRUSTED_MODIFIED":
                status_str = f"{TerminalTheme.BRIGHT_RED}⚠️ MODIFIED{TerminalTheme.RESET}"
            else:
                status_str = f"{TerminalTheme.YELLOW}🆕 NEW{TerminalTheme.RESET}"
                
            desc = s.description[:50] + "..." if len(s.description) > 50 else s.description
            rows.append([name, status_str, desc])

        table_str = BoxRenderer.render_table(headers, rows)
        print("\n" + BoxRenderer.render_panel("⚡ REGISTERED SKILLS & PLUGINS", table_str.splitlines(), color=TerminalTheme.YELLOW))
        print(f"{TerminalTheme.DIM}Tip: Execute with '/<skill_name> <instructions>' or approve with '/skill approve all'{TerminalTheme.RESET}")

    def _handle_list_projects(self):
        """Renders projects table with active indicator."""
        projs = self.orchestrator.workspace.list_projects()
        active_proj = self.orchestrator.workspace.project_name
        
        headers = ["Project Name", "Status", "Codebase Path"]
        rows = []
        for p in projs:
            is_active = (p == active_proj)
            status = f"{TerminalTheme.BRIGHT_GREEN}● ACTIVE{TerminalTheme.RESET}" if is_active else f"{TerminalTheme.DIM}○ Inactive{TerminalTheme.RESET}"
            path = f"projects/{p}/"
            rows.append([p, status, path])

        table_str = BoxRenderer.render_table(headers, rows)
        print("\n" + BoxRenderer.render_panel("📁 PROJECT WORKSPACES (Claude-Style)", table_str.splitlines(), color=TerminalTheme.CYAN))
        print(f"{TerminalTheme.DIM}Tip: Switch projects with 'switch project <name>' or create with 'create project <name>'{TerminalTheme.RESET}")

    def _handle_list_tasks(self):
        """Renders task history in a structured table."""
        tasks = self.orchestrator.task_manager.list_tasks()
        if not tasks:
            print(f"\n{TerminalTheme.DIM}No past task sessions recorded in tasks/{TerminalTheme.RESET}")
            return

        headers = ["Task ID", "Status", "Goal Snippet"]
        rows = []
        for t in reversed(tasks[-10:]):
            status_badge = TerminalTheme.status_badge(t.get("status", "UNKNOWN"))
            goal = t.get("goal", "")[:50] + "..." if len(t.get("goal", "")) > 50 else t.get("goal", "")
            rows.append([t.get("task_id", ""), status_badge, goal])

        table_str = BoxRenderer.render_table(headers, rows)
        print("\n" + BoxRenderer.render_panel("📜 RECENT TASK SESSIONS", table_str.splitlines(), color=TerminalTheme.BLUE))
        print(f"{TerminalTheme.DIM}Tip: View full task audit memory with '/task <task_id>'{TerminalTheme.RESET}")

    def _handle_help_menu(self):
        """Displays categorized slash commands palette."""
        help_lines = [
            f"{TerminalTheme.BOLD}{TerminalTheme.BRIGHT_CORAL}⚡ Core Autonomous Commands:{TerminalTheme.RESET}",
            f"  {TerminalTheme.BRIGHT_CYAN}new{TerminalTheme.RESET}, {TerminalTheme.BRIGHT_CYAN}+ new{TerminalTheme.RESET}           : Start a fresh task session with clean working memory",
            f"  {TerminalTheme.BRIGHT_CYAN}/twin{TerminalTheme.RESET}                 : View and edit Tier 4 AI Twin persona and verified facts",
            f"  {TerminalTheme.BRIGHT_CYAN}/budget{TerminalTheme.RESET}               : Inspect active token limits, step budgets, and loop safety",
            f"  {TerminalTheme.BRIGHT_CYAN}/kill{TerminalTheme.RESET}, {TerminalTheme.BRIGHT_CYAN}/stop{TerminalTheme.RESET}           : Instant out-of-band emergency stop for all running agents",
            f"",
            f"{TerminalTheme.BOLD}{TerminalTheme.BRIGHT_CORAL}📁 Project & Codebase Management:{TerminalTheme.RESET}",
            f"  {TerminalTheme.BRIGHT_CYAN}projects{TerminalTheme.RESET}              : List all isolated project codebases",
            f"  {TerminalTheme.BRIGHT_CYAN}create project <name>{TerminalTheme.RESET} : Create a brand new project and switch to it",
            f"  {TerminalTheme.BRIGHT_CYAN}switch project <name>{TerminalTheme.RESET} : Switch active project context",
            f"  {TerminalTheme.BRIGHT_CYAN}project{TerminalTheme.RESET}               : View current project architecture and memory",
            f"",
            f"{TerminalTheme.BOLD}{TerminalTheme.BRIGHT_CORAL}⚡ Skills & MCP Plugins:{TerminalTheme.RESET}",
            f"  {TerminalTheme.BRIGHT_CYAN}skills{TerminalTheme.RESET}                : List all registered and approved skills",
            f"  {TerminalTheme.BRIGHT_CYAN}/skill promote <name>{TerminalTheme.RESET} : Promote completed task into a permanent skill",
            f"  {TerminalTheme.BRIGHT_CYAN}/skill approve all{TerminalTheme.RESET}     : Hash-lock and approve all registered skills",
            f"  {TerminalTheme.BRIGHT_CYAN}/<skill_name> <query>{TerminalTheme.RESET} : Execute an explicit registered skill directly",
            f"  {TerminalTheme.BRIGHT_CYAN}/mcp{TerminalTheme.RESET}                  : Inspect connected MCP protocol tools",
            f"  {TerminalTheme.BRIGHT_CYAN}/mcp approve <s v>{TerminalTheme.RESET}     : Hash-lock and approve new MCP tool schemas",
            f"",
            f"{TerminalTheme.BOLD}{TerminalTheme.BRIGHT_CORAL}📜 Task Auditing & Exit:{TerminalTheme.RESET}",
            f"  {TerminalTheme.BRIGHT_CYAN}tasks{TerminalTheme.RESET}                 : List past task runs and status",
            f"  {TerminalTheme.BRIGHT_CYAN}task <id>{TerminalTheme.RESET}              : View full task_memory.md for a specific task",
            f"  {TerminalTheme.BRIGHT_CYAN}exit{TerminalTheme.RESET}, {TerminalTheme.BRIGHT_CYAN}quit{TerminalTheme.RESET}              : Gracefully quit Nava OS Shell"
        ]
        print("\n" + BoxRenderer.render_panel("NAVA OS COMMAND PALETTE", help_lines, color=TerminalTheme.CORAL, icon="📖"))

    def _execute_goal_with_tree(self, goal: str):
        """Executes goal through the orchestrator."""
        self.orchestrator.execute(goal)
