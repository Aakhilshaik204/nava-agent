import os
from typing import Any, Optional, Dict, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from nava.core.boot import NavaBootstrapper
from nava.agents.planner import GoalPlanner
from nava.agents.factory import AgentFactory
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.governance.risk_engine import DefaultRiskEngine
from nava.governance.hitl_manager import SingleApprovalManager
from nava.core.ledger import JsonlAuditLedger
from nava.core.schemas import PolicyRule, Outcome, RiskTier, AgentStatus
from nava.tools.executor import LocalToolExecutor
from tests.utils import build_test_gateway
from nava.agents.runtime.file_agent_variants import build_document_agent, build_data_agent, build_verifier_agent
from nava.agents.runtime.nava_agent import build_nava_agent
from nava.agents.runtime.file_agent import build_file_agent

from nava.skills.manager import SkillManager

class Orchestrator:
    def __init__(self, config_path: str = "nava.yaml"):
        bootstrapper = NavaBootstrapper(config_path)
        self.root_agent, self.budget = bootstrapper.bootstrap()
        
        import threading
        self._emergency_stop_event = threading.Event()
        self.skill_manager = SkillManager()
        from nava.skills.promotion import SkillPromoter
        self.skill_promoter = SkillPromoter(self.skill_manager)
        self.ledger = JsonlAuditLedger("nava_audit.jsonl")
        self.registry = ToolRegistry()
        
        # Load security feature switches from nava.yaml if present
        sec_switches = None
        try:
            import yaml
            if os.path.exists("nava.yaml"):
                with open("nava.yaml", "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f)
                    sec_switches = cfg.get("security_switches")
        except Exception:
            pass
            
        self.policy = DefaultPolicyEngine(security_switches=sec_switches)
        
        # Load default wide-open policy for testing
        self.policy.load_rules([
            PolicyRule(rule_id="1", scope="filesystem.write", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="2", scope="filesystem.read", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="3", scope="data.analyze", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="4", scope="test.run", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="5", scope="gmail.read", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="6", scope="browser.navigate", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="7", scope="browser.read", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="8", scope="browser.click", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="9", scope="browser.save_to_scratch", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="10", scope="desktop.read", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="11", scope="desktop.click", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="12", scope="desktop.type", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="13", scope="terminal.execute", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="14", scope="search.web", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="15", scope="memory.semantic", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="16", scope="git.read", condition="", outcome=Outcome.ALLOW, priority=1)
        ])
        
        self.budget_engine = DefaultBudgetEngine()
        self.budget_engine.register_budget(self.budget)
        
        from nava.memory.store import ProfileMemoryStore, SemanticMemoryStore, EpisodicMemoryStore
        from nava.memory.ai_twin import AITwinManager
        self.profile_store = ProfileMemoryStore("memory/profile.json")
        self.semantic_store = SemanticMemoryStore("memory/semantic.json")
        self.episodic_store = EpisodicMemoryStore("memory/episodic.json")
        self.ai_twin = AITwinManager(self.profile_store)
        self.risk = DefaultRiskEngine(self.profile_store)
        
        self.hitl = SingleApprovalManager()
        self.register_tools()
        self.factory = AgentFactory(self.registry, self.policy, self.budget_engine)
        
        from nava.credentials.vault import CredentialVault
        from nava.credentials.broker import CredentialBroker
        from nava.workspace.project_manager import ProjectWorkspace
        from nava.core.message_bus import AgentMessageBus
        self.vault = CredentialVault()
        self.credential_broker = CredentialBroker(self.vault)
        self.workspace = ProjectWorkspace(root_dir=os.getcwd())
        self.workspace.initialize_project_memory()
        self.message_bus = AgentMessageBus()
        
        from nava.tools.mcp_client import MCPClientManager
        self.mcp_manager = MCPClientManager(self.registry, credential_broker=self.credential_broker)
        import sys
        self.mcp_manager.register_server(
            name="gmail",
            command=sys.executable,
            args=["src/nava/tools/mcp_gmail_server.py"],
            required_service="gmail"
        )
        
        from nava.governance.state_observer import DefaultStateObserver
        self.state_observer = DefaultStateObserver()
        
        self.planner = GoalPlanner(
            available_templates=["DocumentAgent", "DataAgent", "VerifierAgent", "CodingAgent", "ReviewerAgent", "UniversalFileAgent", "BrowserAgent", "ResearchAgent", "TerminalAgent", "ComputerAgent"],
            ceiling_tools=self.root_agent.tool_scope,
            ceiling_permissions=self.root_agent.permission_scope,
            budget_engine=self.budget_engine,
            registry=self.registry
        )
        
    def register_tools(self):
        self.registry.register_tool(ToolDefinition(
            name="system.read_skill", description="Reads the full instructional content of a skill.",
            input_schema={"skill_name": "string"}, output_schema={"success": "boolean", "content": "string"},
            permissions_required=["system.read_skill"], risk_level=RiskTier.LOW, reversible=True
        ))
        
        # Register the mock.send_wire_transfer for Phase 7 testing
        self.registry.register_tool(ToolDefinition(
            name="mock.send_wire_transfer", description="Sends a mock wire transfer (Irreversible)",
            input_schema={"amount": "number", "account_id": "string"}, output_schema={"success": "boolean"},
            permissions_required=["mock.send_wire_transfer"], risk_level=RiskTier.CRITICAL, reversible=False
        ))
        
        self.registry.register_tool(ToolDefinition(
            name="file.delete", description="Deletes a file",
            input_schema={"filename": "string"}, output_schema={"success": "boolean", "message": "string"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.MEDIUM, reversible=False
        ))
        # Register the compensation allowlist tools
        self.registry.register_tool(ToolDefinition(
            name="mock.notify_admin", description="Notifies an admin of an error",
            input_schema={"message": "string"},
            output_schema={"success": "boolean"},
            permissions_required=["*"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="system.flag_review", description="Flags a task for review",
            input_schema={"task_id": "string", "reason": "string"},
            output_schema={"success": "boolean"},
            permissions_required=["*"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="file.write", description="Writes a text file to disk",
            input_schema={"filename": "string", "content": "string"},
            output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ))

        self.registry.register_tool(ToolDefinition(
            name="file.create_pdf", description="Creates a beautiful PDF file. For simple reports, use 'markdown_content'. For advanced, highly-styled reports with metric boxes and grids (like an Executive Report), use 'html_content' and 'custom_css' (Note: xhtml2pdf uses HTML tables for grids, not flexbox).",
            input_schema={
                "filename": "string", 
                "source_file": "string (optional, path to file to read from)",
                "markdown_content": "string (optional)",
                "html_content": "string (optional, overrides markdown)",
                "custom_css": "string (optional, CSS to inject)",
                "primary_color": "string (hex code)",
                "font_family": "string"
            },
            output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="file.create_docx", description="Creates a DOCX file on disk. You can either provide 'content' directly, OR provide a 'source_file' path to read the content from disk automatically (strongly preferred for large files to avoid context limits).",
            input_schema={"filename": "string", "content": "string (optional)", "source_file": "string (optional, path to file to read from)"},
            output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="file.create_pptx", description="Creates a visually stunning, Gamma-style PPTX presentation.",
            input_schema={
                "filename": "string", 
                "theme": "object with keys: bg_color (hex), title_color (hex), text_color (hex), accent_color (hex)",
                "slides": "array of objects. Each slide must have 'layout' (choices: 'title_slide', 'standard', 'two_column', 'metrics_3'), 'title' (string), and optionally 'content' (string for standard), 'left_content' & 'right_content' (strings for two_column), or 'metrics' (array of objects with 'label' and 'value' for metrics_3)."
            },
            output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="file.read", description="Reads a file from disk",
            input_schema={"filename": "string"},
            output_schema={"content": "string"},
            permissions_required=["filesystem.read"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="data.analyze", description="Analyzes data",
            input_schema={"filename": "string"},
            output_schema={"row_count": "integer", "columns": "integer"},
            permissions_required=["filesystem.read", "data.analyze"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="test.run", description="Runs a test command",
            input_schema={"command": "string"},
            output_schema={"stdout": "string", "stderr": "string"},
            permissions_required=["test.run"], risk_level=RiskTier.MEDIUM, reversible=False
        ))
        self.registry.register_tool(ToolDefinition(
            name="code.replace_content", description="Replaces a specific string of code in a file.",
            input_schema={"filename": "string", "target_content": "string", "replacement_content": "string"},
            output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"], 
            risk_level=RiskTier.LOW, 
            reversible=True,
            rollback_strategy="restore_from_pre_write_snapshot"
        ))
        self.registry.register_tool(ToolDefinition(
            name="code.search", description="Search for a string across all files in a directory.",
            input_schema={"query": "string", "directory": "string"},
            output_schema={"results": "string"},
            permissions_required=["filesystem.read"], 
            risk_level=RiskTier.LOW, 
            reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="code.read_directory_tree", description="Get a structural overview of a directory tree.",
            input_schema={"directory": "string"},
            output_schema={"tree": "string"},
            permissions_required=["filesystem.read"], 
            risk_level=RiskTier.LOW, 
            reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="code.diff_review", description="Gets the git diff of a file or the whole repo.",
            input_schema={"filename": "string"},
            output_schema={"diff": "string"},
            permissions_required=["filesystem.read"], 
            risk_level=RiskTier.LOW, 
            reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="code.replace_content_batch", description="Transactional replacement across multiple files.",
            input_schema={"edits": "array"},
            output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"], 
            risk_level=RiskTier.MEDIUM, 
            reversible=True,
            rollback_strategy="transactional_restore_from_pre_write_snapshot"
        ))
        self.registry.register_tool(ToolDefinition(
            name="code.find_references", description="Find external references/callers of a function.",
            input_schema={"function_name": "string"},
            output_schema={"results": "string"},
            permissions_required=["filesystem.read"], 
            risk_level=RiskTier.LOW, 
            reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="shell.execute", description="Execute arbitrary shell commands in a sandbox.",
            input_schema={"command": "string"},
            output_schema={"returncode": "integer"},
            permissions_required=["shell.execute"], 
            risk_level=RiskTier.CRITICAL, 
            reversible=False
        ))
        
        self.registry.register_tool(ToolDefinition(
            name="browser.navigate", description="Navigate to a URL. Blocked for file://, localhost, and private IPs.",
            input_schema={"url": "string"}, output_schema={"result": "string"},
            permissions_required=["browser.navigate"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="browser.extract_dom", description="Extract the raw HTML DOM of the current page. WARNING: Returns massive noisy HTML. Prefer browser.extract_text for readable content.",
            input_schema={}, output_schema={"html": "string"},
            permissions_required=["browser.read"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="browser.extract_text", description="Extract only the readable text content from the current page, with ads/navs/scripts/trackers removed. Returns clean text ideal for summarization and saving. PREFERRED over extract_dom.",
            input_schema={}, output_schema={"text": "string"},
            permissions_required=["browser.read"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="browser.click", description="Click an element on the current page using a CSS selector. The element will be visually highlighted before clicking.",
            input_schema={"selector": "string"}, output_schema={"result": "string"},
            permissions_required=["browser.click"], risk_level=RiskTier.MEDIUM, reversible=False
        ))
        self.registry.register_tool(ToolDefinition(
            name="browser.type", description="Type text into an input field using a CSS selector. Refuses to type sensitive data (API keys, passwords).",
            input_schema={"selector": "string", "text": "string"}, output_schema={"result": "string"},
            permissions_required=["browser.type"], risk_level=RiskTier.MEDIUM, reversible=False
        ))
        self.registry.register_tool(ToolDefinition(
            name="browser.scroll", description="Scroll down the page by the specified number of pixels to load more content or read below the fold.",
            input_schema={"pixels": "integer (default 800)"}, output_schema={"result": "string"},
            permissions_required=["browser.scroll"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="browser.go_back", description="Navigate back to the previous page (like pressing the browser back button). Useful for returning to search results after reading an article.",
            input_schema={}, output_schema={"result": "string"},
            permissions_required=["browser.navigate"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="browser.get_url", description="Get the current page URL.",
            input_schema={}, output_schema={"url": "string"},
            permissions_required=["browser.read"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="browser.save_to_scratch", description="Safely append sanitized extracted text to an ephemeral scratch file. Returns the system-generated filepath (e.g. scratch/agt-xxxx_extraction.md). You MUST pass this filepath to downstream agents.",
            input_schema={"text": "string"}, output_schema={"success": "boolean", "bytes_written": "integer", "file": "string"},
            permissions_required=["browser.save_to_scratch"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="desktop.screenshot", description="Takes a full OS display screenshot and returns the file path.",
            input_schema={"path": "string (optional)"}, output_schema={"screenshot_path": "string"},
            permissions_required=["desktop.read"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="desktop.click", description="Moves the mouse cursor to (x, y) coordinates and performs a click or double-click.",
            input_schema={"x": "integer", "y": "integer", "button": "string (optional: left/right)", "double": "boolean (optional)"}, output_schema={"result": "string"},
            permissions_required=["desktop.click"], risk_level=RiskTier.HIGH, reversible=False
        ))
        self.registry.register_tool(ToolDefinition(
            name="desktop.type", description="Types text into the currently active desktop window. Refuses sensitive credential patterns.",
            input_schema={"text": "string"}, output_schema={"result": "string"},
            permissions_required=["desktop.type"], risk_level=RiskTier.HIGH, reversible=False
        ))
        self.registry.register_tool(ToolDefinition(
            name="desktop.hotkey", description="Presses a keyboard key combination (e.g. ['ctrl', 's'] or 'enter').",
            input_schema={"keys": "array of strings or string combination"}, output_schema={"result": "string"},
            permissions_required=["desktop.type"], risk_level=RiskTier.MEDIUM, reversible=False
        ))
        self.registry.register_tool(ToolDefinition(
            name="desktop.get_screen_size", description="Returns the primary screen display resolution (width and height).",
            input_schema={}, output_schema={"width": "integer", "height": "integer"},
            permissions_required=["desktop.read"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="search.web", description="Searches the web via DuckDuckGo and returns structured snippets and URLs.",
            input_schema={"query": "string"}, output_schema={"query": "string", "results": "array"},
            permissions_required=["search.web"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="memory.semantic_ingest", description="Ingests synthesized research facts into Tier 3 Semantic Memory.",
            input_schema={"content": "string", "source": "string (optional)", "tags": "array (optional)"}, output_schema={"success": "boolean", "entry_id": "string"},
            permissions_required=["memory.semantic"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="terminal.execute", description="Executes a command inside the terminal sandbox, capturing exit code and outputs.",
            input_schema={"command": "string"}, output_schema={"returncode": "integer", "stdout": "string", "stderr": "string"},
            permissions_required=["terminal.execute"], risk_level=RiskTier.HIGH, reversible=False
        ))
        self.registry.register_tool(ToolDefinition(
            name="git.status", description="Returns git branch, staged, modified, and untracked files.",
            input_schema={}, output_schema={"branch": "string", "status_output": "string"},
            permissions_required=["git.read"], risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="git.diff", description="Returns unified git diff of working directory or staged changes.",
            input_schema={"staged": "boolean (optional)"}, output_schema={"diff": "string", "lines_count": "integer"},
            permissions_required=["git.read"], risk_level=RiskTier.LOW, reversible=True
        ))
    def execute(self, goal: str):
        print(f"--- Nava Orchestrator ---")
        print(f"Objective: {goal}")
               # 1. Check for explicit slash commands
        explicit_skill_context = ""
        if goal.startswith("/"):
            parts = goal.split(" ", 2)
            cmd = parts[0][1:] # remove '/'
            
            if cmd == "mcp" and len(parts) >= 3 and parts[1] == "approve":
                target_args = parts[2].split(" ")
                if len(target_args) < 2:
                    print("Usage: /mcp approve <server_name> <tool_name>")
                    return
                server_name, tool_name = target_args[0], target_args[1]
                
                try:
                    pending_tools = self.mcp_manager.pending_tools.get(server_name, {})
                    if tool_name not in pending_tools:
                        print(f"No pending tool '{tool_name}' found for server '{server_name}'.")
                        return
                        
                    tool_dict = pending_tools[tool_name]
                    trust_state = tool_dict.get("trust_state")
                    
                    if trust_state == "TRUSTED":
                        print(f"Tool '{tool_name}' is already TRUSTED.")
                        return
                        
                    import json
                    canonical_dict = {
                        "name": tool_dict.get("name", ""),
                        "description": tool_dict.get("description", ""),
                        "input_schema": tool_dict.get("input_schema", {}),
                        "permissions_required": tool_dict.get("permissions_required", []),
                        "risk_level": tool_dict.get("risk_level", "MEDIUM"),
                        "reversible": tool_dict.get("reversible", True),
                        "required_credentials": tool_dict.get("required_credentials", [])
                    }
                    new_content = json.dumps(canonical_dict, indent=2)
                    
                    if trust_state == "UNTRUSTED_NEW":
                        print(f"\n--- NEW MCP TOOL DETECTED: {server_name}::{tool_name} ---")
                        print(new_content)
                        print("-" * 40)
                        
                        dangerous_keywords = ["shell.execute", "file.delete", "mock.send_wire_transfer", "password", "token", "key", "~/.ssh"]
                        warning_fired = any(k in new_content.lower() for k in dangerous_keywords)
                        if warning_fired:
                            print("\033[91m[WARNING: Dangerous keyword detected in new tool schema!]\033[0m")
                            ans = input("DANGEROUS KEYWORDS DETECTED. Type 'AUTHORIZE' to approve this tool: ")
                            is_approved = (ans == 'AUTHORIZE')
                        else:
                            ans = input("Approve this new MCP tool? [y/N]: ")
                            is_approved = (ans.lower() == 'y')
                            
                        if is_approved:
                            self.mcp_manager.approve_tool(server_name, tool_name, actor="local_user")
                            from nava.core.schemas import Event
                            import uuid
                            evt = Event(event_id=f"evt-{uuid.uuid4().hex[:8]}", event_type="MCP_TOOL_APPROVED", task_id="system", payload={"server": server_name, "tool": tool_name, "state": "NEW", "actor": "local_user"})
                            self.ledger.append_event(evt)
                        return
                        
                    if trust_state == "UNTRUSTED_MODIFIED":
                        old_content = self.mcp_manager.get_ledger_content(server_name, tool_name) or ""
                        
                        import difflib
                        diff = list(difflib.unified_diff(old_content.splitlines(), new_content.splitlines(), lineterm=""))
                        
                        print(f"\n--- MCP TOOL MODIFIED: {server_name}::{tool_name} ---")
                        dangerous_keywords = ["shell.execute", "file.delete", "mock.send_wire_transfer", "password", "token", "key", "~/.ssh"]
                        warning_fired = False
                        for line in diff:
                            if line.startswith("+"):
                                if any(k in line.lower() for k in dangerous_keywords):
                                    print(f"\033[91m[WARNING: Dangerous keyword detected]\033[0m {line}")
                                    warning_fired = True
                                else:
                                    print(f"\033[92m{line}\033[0m")
                            elif line.startswith("-"):
                                print(f"\033[91m{line}\033[0m")
                            else:
                                print(line)
                                
                        print("-" * 40)
                        if warning_fired:
                            ans = input("DANGEROUS KEYWORDS DETECTED. Type 'AUTHORIZE' to approve these changes: ")
                            is_approved = (ans == 'AUTHORIZE')
                        else:
                            ans = input("Approve these schema changes? [y/N]: ")
                            is_approved = (ans.lower() == 'y')
                            
                        if is_approved:
                            self.mcp_manager.approve_tool(server_name, tool_name, actor="local_user")
                            from nava.core.schemas import Event
                            import uuid
                            evt = Event(event_id=f"evt-{uuid.uuid4().hex[:8]}", event_type="MCP_TOOL_APPROVED", task_id="system", payload={"server": server_name, "tool": tool_name, "state": "MODIFIED", "actor": "local_user"})
                            self.ledger.append_event(evt)
                        return
                except Exception as e:
                    print(f"Error approving MCP tool: {e}")
                    return

            if cmd == "plugin" and len(parts) >= 3 and parts[1] == "approve":
                skill_name = parts[2]
                skill = self.skill_manager.get_skill(skill_name)
                if not skill:
                    print(f"Skill '{skill_name}' not found.")
                    return
                
                if skill.trust_state == "TRUSTED":
                    print(f"Skill '{skill_name}' is already TRUSTED.")
                    return
                    
                if skill.trust_state == "UNTRUSTED_NEW":
                    print(f"\n--- NEW PLUGIN DETECTED: {skill_name} ---")
                    print(skill.content)
                    print("-" * 40)
                    ans = input("Approve this new plugin? [y/N]: ")
                    if ans.lower() == 'y':
                        self.skill_manager.approve_skill(skill_name)
                        # Log to Audit Ledger
                        from nava.core.schemas import Event
                        import uuid
                        evt = Event(event_id=f"evt-{uuid.uuid4().hex[:8]}", event_type="PLUGIN_APPROVED", task_id="system", payload={"plugin": skill_name, "state": "NEW", "actor": "local_user"})
                        self.ledger.append_event(evt)
                    return
                    
                if skill.trust_state == "UNTRUSTED_MODIFIED":
                    old_content = self.skill_manager.get_ledger_content(skill_name) or ""
                    new_content = skill.content
                    
                    import difflib
                    diff = list(difflib.unified_diff(old_content.splitlines(), new_content.splitlines(), lineterm=""))
                    
                    print(f"\n--- PLUGIN MODIFIED: {skill_name} ---")
                    dangerous_keywords = ["shell.execute", "file.delete", "mock.send_wire_transfer", "password", "token", "key", "~/.ssh"]
                    warning_fired = False
                    for line in diff:
                        if line.startswith("+"):
                            # Simple scanner for dangerous additions
                            if any(k in line for k in dangerous_keywords):
                                print(f"\033[91m[WARNING: Dangerous keyword detected]\033[0m {line}")
                                warning_fired = True
                            else:
                                print(f"\033[92m{line}\033[0m")
                        elif line.startswith("-"):
                            print(f"\033[91m{line}\033[0m")
                        else:
                            print(line)
                            
                    print("-" * 40)
                    if warning_fired:
                        ans = input("DANGEROUS KEYWORDS DETECTED. Type 'AUTHORIZE' to approve these changes: ")
                        is_approved = (ans == 'AUTHORIZE')
                    else:
                        ans = input("Approve these changes? [y/N]: ")
                        is_approved = (ans.lower() == 'y')
                        
                    if is_approved:
                        self.skill_manager.approve_skill(skill_name)
                        from nava.core.schemas import Event
                        import uuid
                        evt = Event(event_id=f"evt-{uuid.uuid4().hex[:8]}", event_type="PLUGIN_APPROVED", task_id="system", payload={"plugin": skill_name, "state": "MODIFIED", "actor": "local_user"})
                        self.ledger.append_event(evt)
                    return

            # Otherwise, assume it's a skill execution command
            skill_cmd = cmd
            query = " ".join(parts[1:]) if len(parts) > 1 else ""
            
            print(f"[Orchestrator] Detected explicit skill command: /{skill_cmd}")
            skill = self.skill_manager.get_skill(skill_cmd)
            if skill:
                if skill.trust_state != "TRUSTED":
                    print(f"\n[!] SECURITY BLOCK: Skill '{skill_cmd}' is in state {skill.trust_state}.")
                    print(f"Refusing to execute unverified instructional content.")
                    print(f"Run '/plugin approve {skill_cmd}' to review and authorize it.\n")
                    return
                    
                print(f"[Orchestrator] Activating skill: {skill.name}")
                explicit_skill_context = f"\n[EXPLICIT SKILL INSTRUCTIONS: {skill.name}]\n{skill.content}\n"
                goal = query # update goal to just the query
            else:
                print(f"[Orchestrator] Warning: Skill '{skill_cmd}' not found.")
                
        # 2. Add Skill Catalog to prompt if no explicit skill was forced
        if not explicit_skill_context:
            catalog = self.skill_manager.get_catalog_string()
            explicit_skill_context = f"\n[SKILL CATALOG]\n{catalog}\nYou may use the 'system.read_skill' tool to read the full content of any skill listed above. (Only TRUSTED skills are shown).\n"

        # 3. Inject Project Continuity Context if available
        project_context = ""
        if hasattr(self, 'workspace'):
            resume_ctx = self.workspace.get_resume_context()
            if resume_ctx:
                project_context = f"\n{resume_ctx}\n"

        print("Planning...")
        
        # Inject skill context & project context into the objective for the planner
        enhanced_objective = f"{goal}\n{explicit_skill_context}\n{project_context}".strip()
        
        agent_specs = self.planner.plan(enhanced_objective, self.root_agent.agent_id, budget_ref=self.root_agent.budget_ref)
        
        # 2. Execute
        # Retrieve recent episodic memories to provide cross-session context
        from nava.memory.store import EpisodicMemoryStore
        epi_store = EpisodicMemoryStore("memory/episodic.json")
        recent_memories = [str(r.content) for r in epi_store.get_recent(limit=3)]
        
        global_payload = {
            "context": f"Overall Objective: {goal}\n{explicit_skill_context}",
            "recent_episodic_memory": recent_memories
        }
        
        import threading
        import concurrent.futures
        payload_lock = threading.Lock()
        
        if not hasattr(self, 'lock_manager'):
            from nava.governance.lock_manager import DefaultLockManager
            self.lock_manager = DefaultLockManager()

        # Group agent specs by execution stage
        stages = {}
        for i, spec in enumerate(agent_specs):
            stg = getattr(spec, 'stage', 1) or 1
            stages.setdefault(stg, []).append((i, spec))
            
        sorted_stages = sorted(stages.keys())
        
        for stg in sorted_stages:
            stage_items = stages[stg]
            can_parallel = len(stage_items) > 1 and all(getattr(s, 'is_parallel', True) for _, s in stage_items)
            
            if can_parallel:
                print(f"\n=======================================================")
                print(f"  EXECUTING STAGE {stg} IN PARALLEL ({len(stage_items)} Dynamic Agents)")
                print(f"=======================================================")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(stage_items), 8)) as executor:
                    future_to_spec = {
                        executor.submit(self._execute_single_agent, spec, idx, len(agent_specs), global_payload, payload_lock): (idx, spec)
                        for idx, spec in stage_items
                    }
                    for future in concurrent.futures.as_completed(future_to_spec):
                        idx, spec = future_to_spec[future]
                        try:
                            future.result()
                        except Exception as e:
                            print(f"[!] Error in parallel worker for Stage {stg} ({spec.requested_role}): {e}")
            else:
                for idx, spec in stage_items:
                    self._execute_single_agent(spec, idx, len(agent_specs), global_payload, payload_lock)

        # Log successful completion to Episodic Memory
        try:
            from nava.memory.store import EpisodicMemoryStore
            from nava.core.schemas import MemoryRecord, MemoryTier, MemoryTrustLevel
            import uuid
            
            epi_store = EpisodicMemoryStore("memory/episodic.json")
            record = MemoryRecord(
                memory_id=f"epi-{uuid.uuid4().hex[:8]}",
                tier=MemoryTier.EPISODIC,
                content={"event": "OBJECTIVE_COMPLETED", "objective": goal, "payload_summary": list(global_payload.keys())},
                source="orchestrator",
                confidence=1.0,
                importance=0.8,
                sensitivity="low",
                trust_level=MemoryTrustLevel.VERIFIED,
                provenance=["orchestrator"]
            )
            epi_store.store(record)
            print("\n-> Orchestrator: Logged session completion to Episodic Memory.")
        except Exception as e:
            print(f"Failed to log episodic memory: {e}")
            
        import glob
        for f in glob.glob("scratch/*_extraction.md"):
            try:
                os.remove(f)
                print(f"[Teardown] Cleaned up ephemeral extraction file: {f}")
            except Exception as e:
                pass
        
        # Record execution checkpoint into ProjectWorkspace
        if hasattr(self, 'workspace'):
            try:
                import uuid
                touched_files = [f for f in os.listdir(".") if os.path.isfile(f) and f.endswith(('.md', '.py', '.txt', '.pdf', '.docx', '.pptx', '.json', '.html'))]
                self.workspace.save_checkpoint(
                    task_id=f"tsk-{uuid.uuid4().hex[:6]}",
                    objective=goal,
                    last_agent="OrchestratorSwarm",
                    touched_files=touched_files[-5:],
                    status="READY_TO_RESUME"
                )
                print("[ProjectWorkspace] Checkpoint recorded in .nava/project_memory.md")
            except Exception as e:
                pass
        
        print(f"\n--- Objective Execution Finished ---\n")

    def _execute_single_agent(self, spec, index: int, total_specs: int, global_payload: dict, payload_lock: Any):
        print(f"\n[{index+1}/{total_specs}] Spawning {spec.requested_role} ({spec.display_label or spec.requested_role}) for goal: {spec.goal}")
        
        try:
            child_agent = self.factory.spawn_agent(spec, self.root_agent)
        except Exception as e:
            print(f"Failed to spawn agent: {e}")
            return {"success": False, "error": str(e)}
            
        from nava.core.ledger import LocalFileReceiptStore
        receipt_store = LocalFileReceiptStore("receipts")
        
        gateway = build_test_gateway(
            self.registry, self.policy, self.risk, self.budget_engine, 
            self.hitl, self.ledger, child_agent, 
            receipt_store=receipt_store,
            concurrency_manager=self.lock_manager,
            credential_broker=self.credential_broker,
            state_observer=self.state_observer
        )
        if hasattr(self, '_emergency_stop_event'):
            gateway._emergency_event = self._emergency_stop_event
        if not hasattr(self, '_shared_executor'):
            self._shared_executor = LocalToolExecutor(mcp_manager=self.mcp_manager, skill_manager=self.skill_manager)
        gateway.executor = self._shared_executor
        
        from nava.agents.runtime.coding_agent import build_coding_agent
        from nava.agents.runtime.reviewer_agent import build_reviewer_agent
        from nava.agents.runtime.file_agent_variants import build_document_agent, build_data_agent, build_verifier_agent
        from nava.agents.runtime.file_agent import build_file_agent
        from nava.agents.runtime.nava_agent import build_nava_agent
        
        if child_agent.role == "DocumentAgent":
            graph = build_document_agent()
        elif child_agent.role == "DataAgent":
            graph = build_data_agent()
        elif child_agent.role == "VerifierAgent":
            graph = build_verifier_agent()
        elif child_agent.role == "UniversalFileAgent":
            graph = build_file_agent()
        elif child_agent.role == "CodingAgent":
            graph = build_coding_agent(self.registry)
        elif child_agent.role == "ReviewerAgent":
            graph = build_reviewer_agent(self.registry)
        elif child_agent.role == "BrowserAgent":
            from nava.agents.runtime.browser_agent import build_browser_agent
            graph = build_browser_agent(self.registry)
        elif child_agent.role == "ResearchAgent":
            from nava.agents.runtime.research_agent import build_research_agent
            graph = build_research_agent(self.registry)
        elif child_agent.role == "ComputerAgent":
            from nava.agents.runtime.computer_agent import build_computer_agent
            graph = build_computer_agent(self.registry)
        elif child_agent.role == "TerminalAgent":
            from nava.agents.runtime.terminal_agent import build_terminal_agent
            graph = build_terminal_agent(self.registry)
        elif child_agent.role == "DynamicAgent":
            from nava.agents.runtime.dynamic_agent import build_dynamic_agent
            graph = build_dynamic_agent(self.registry)
        else:
            graph = build_nava_agent()
            
        with payload_lock:
            payload_copy = dict(global_payload)
            
        initial_state = {
            "agent_state": child_agent,
            "payload": payload_copy,
            "plan": None,
            "tool_requests": [],
            "receipts": [],
            "is_success": False,
            "gateway": gateway,
            "message_bus": getattr(self, "message_bus", None),
            "history": []
        }
        
        if child_agent.role in ["DocumentAgent", "DataAgent", "VerifierAgent", "UniversalFileAgent"]:
            initial_state["tool_request"] = None
            initial_state["receipt"] = None
        elif child_agent.role in ["CodingAgent", "ReviewerAgent"]:
            initial_state["tool_request"] = None
            initial_state["receipt"] = None
            
        agent_schemas = {}
        for t_name in child_agent.tool_scope:
            t_def = self.registry.get_tool(t_name)
            if t_def:
                agent_schemas[t_name] = t_def.input_schema
        initial_state["payload"]["available_tool_schemas"] = agent_schemas
        
        print(f"Invoking graph for {child_agent.role}...")
        
        try:
            if child_agent.role in ["CodingAgent", "ReviewerAgent", "BrowserAgent", "DynamicAgent"]:
                current_state = initial_state
                while True:
                    current_state = graph.invoke(current_state, config={"recursion_limit": 50})
                    tool_req = current_state.get("tool_request")
                    plan_name = current_state.get("plan")
                    
                    if plan_name == "FINISH":
                        print(f"{child_agent.role} finished its cyclic task.")
                        import json
                        def truncate_result(res):
                            res_str = json.dumps(res) if not isinstance(res, str) else res
                            return res_str[:1500] + "... [TRUNCATED]" if len(res_str) > 1500 else res
                            
                        final_data = current_state.get("final_answer") or current_state.get("observation")
                        with payload_lock:
                            global_payload[f"Step_{index+1}_{child_agent.role}"] = truncate_result(final_data)
                        break
                        
                    if tool_req:
                        print(f"Agent {child_agent.agent_id} requested tool: {tool_req.tool_name}")
                        receipt = gateway.process_request(tool_req)
                        print(f"-> Tool Execution Result: {receipt.result.name}")
                        print(f"-> Data: {receipt.result_data}")
                        
                        if receipt.result.name == "FAILURE":
                            error_str = str(receipt.result_data.get("error", "Unknown error"))
                            if tool_req.tool_name == "test.run":
                                from nava.memory.store import EpisodicMemoryStore
                                from nava.core.schemas import MemoryRecord, MemoryTier, MemoryTrustLevel
                                import uuid
                                epi_store = EpisodicMemoryStore("memory/episodic.json")
                                record = MemoryRecord(
                                    memory_id=f"epi-{uuid.uuid4().hex[:8]}",
                                    tier=MemoryTier.EPISODIC,
                                    content={"event": "TEST_FAILURE", "command": tool_req.arguments, "error": error_str},
                                    trust_level=MemoryTrustLevel.UNVERIFIED,
                                    provenance=["coding_agent_test_loop"]
                                )
                                epi_store.store(record)
                                print("-> Logged failure to EpisodicMemoryStore.")
                            
                            if not self.budget_engine.record_failure(child_agent, error_str):
                                print("\n[!] RUNAWAY LOOP DETECTED (Section 14.4). Same failure state hit 3 times.")
                                print("-> Escalating to ReviewerAgent...")
                                
                                from nava.core.schemas import AgentSpec
                                import datetime, uuid
                                rev_spec = AgentSpec(
                                    request_id=f"req-{uuid.uuid4().hex[:8]}",
                                    requested_role="ReviewerAgent",
                                    goal=f"Analyze why the CodingAgent is stuck in an infinite loop failing with: {error_str}",
                                    parent_agent_id=self.root_agent.agent_id,
                                    requested_tools=["code.diff_review", "file.read"],
                                    requested_permission_scope=["filesystem.read"],
                                    ttl=datetime.timedelta(minutes=10)
                                )
                                try:
                                    rev_agent = self.factory.spawn_agent(rev_spec, self.root_agent)
                                    rev_state = {"agent_state": rev_agent, "payload": dict(global_payload), "history": []}
                                    from nava.agents.runtime.reviewer_agent import build_reviewer_agent
                                    rev_graph = build_reviewer_agent(self.registry)
                                    rev_final = rev_graph.invoke(rev_state)
                                except Exception as e:
                                    print(f"-> Failed to run Reviewer fallback: {e}")
                                
                                print("\n-> Escalating to HITL (Human-in-the-Loop)...")
                                self.hitl.request_approval(
                                    tool_request=tool_req,
                                    assessment=None,
                                    context=f"CodingAgent is stuck on error: {error_str}. Reviewer analysis complete. Please intervene or abort."
                                )
                                break
                        
                        current_state["observation"] = receipt.result_data
                        current_state["tool_request"] = None
            else:
                final_state = graph.invoke(initial_state)
                tool_req = final_state.get("tool_request")
                
                import json
                def truncate_result(res):
                    res_str = json.dumps(res)
                    return res_str[:1500] + "... [TRUNCATED for inter-agent context]" if len(res_str) > 1500 else res

                if tool_req:
                    print(f"Agent {child_agent.agent_id} requested tool: {tool_req.tool_name}")
                    receipt = gateway.process_request(tool_req)
                    print(f"-> Tool Execution Result: {receipt.result.name}")
                    print(f"-> Data: {receipt.result_data}")
                    with payload_lock:
                        global_payload[f"{child_agent.role}_result"] = truncate_result(receipt.result_data)
                
                if final_state.get("receipt"):
                    result_enum = final_state["receipt"].result
                    result_data = final_state["receipt"].result_data
                    print(f"-> Tool Execution Result: {result_enum.name}")
                    print(f"-> Data: {result_data}")
                    with payload_lock:
                        global_payload[f"Step_{index+1}_{child_agent.role}"] = truncate_result(result_data)
                    final_state["is_success"] = (result_enum.name == "SUCCESS")
                elif final_state.get("receipts"):
                    results_data = [r.result_data for r in final_state["receipts"]]
                    print(f"-> Tool Execution Results Data: {results_data}")
                    with payload_lock:
                        global_payload[f"Step_{index+1}_{child_agent.role}"] = truncate_result(results_data)
                    final_state["is_success"] = all(r.result.name == "SUCCESS" for r in final_state["receipts"])
                elif tool_req and 'receipt' in locals():
                    final_state["is_success"] = (receipt.result.name == "SUCCESS")
                    
                if not final_state.get('is_success'):
                    print(f"\n[!] Agent {child_agent.role} failed. Initiating Rollback & Compensation (Phase 7)...")
                    from nava.governance.compensation_engine import CompensationEngine
                    from nava.governance.rollback_engine import RollbackEngine
                    from nava.core.schemas import AgentState, AgentType, TaskBudget
                    import datetime, uuid
                    
                    rbk_budget = TaskBudget(
                        task_id=f"budget-rbk-{uuid.uuid4().hex[:8]}",
                        max_agents=1, max_depth=1, max_steps=5, max_tokens=5000,
                        max_runtime=datetime.timedelta(minutes=5), max_retries=1
                    )
                    self.budget_engine.register_budget(rbk_budget)
                    
                    rbk_agent = AgentState(
                        agent_id="SYSTEM_ROLLBACK",
                        role="SYSTEM_ROLLBACK",
                        type=AgentType.STATIC,
                        goal="Rollback failed task",
                        permission_scope=["*"],
                        credential_scope=[],
                        tool_scope=["*"],
                        depth=0,
                        ttl=datetime.timedelta(minutes=5),
                        expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
                        budget_ref=rbk_budget.task_id
                    )
                    
                    rbk_gateway = build_test_gateway(
                        self.registry, self.policy, self.risk, self.budget_engine, 
                        self.hitl, self.ledger, rbk_agent, 
                        receipt_store=receipt_store,
                        concurrency_manager=self.lock_manager,
                        credential_broker=self.credential_broker,
                        state_observer=self.state_observer
                    )
                    
                    comp_engine = CompensationEngine(rbk_gateway)
                    rollback_engine = RollbackEngine(rbk_gateway, comp_engine)
                    
                    agent_receipts = receipt_store.get_receipts_by_agent(child_agent.agent_id)
                    rollback_engine.rollback(agent_receipts, rbk_budget.task_id)
                    print(f"[Budget Check] SYSTEM_ROLLBACK budget consumed steps: {rbk_budget.consumed_steps}/{rbk_budget.max_steps}")
        finally:
            print(f"-> Tearing down agent: {child_agent.agent_id} ({child_agent.role})")
            child_agent.status = AgentStatus.TERMINATED
            budget = self.budget_engine.budgets.get(child_agent.budget_ref)
            if budget and budget.consumed_agents > 0:
                budget.consumed_agents -= 1
            print(f"-> Teardown complete for {child_agent.agent_id}.")

    def emergency_stop(self, reason: str = "User triggered emergency halt"):
        """
        Emergency Kill Switch (Section 31.4 & Invariant #18):
        Out-of-band immediate shutdown of all in-flight execution.
        """
        print(f"\n=======================================================")
        print(f"  [!] EMERGENCY STOP TRIGGERED: {reason}")
        print(f"=======================================================")
        
        if hasattr(self, '_emergency_stop_event'):
            self._emergency_stop_event.set()
            
        if hasattr(self, 'credential_broker'):
            self.credential_broker.emergency_revoke_all()
            
        if hasattr(self, 'hitl'):
            self.hitl.cancel_all_pending()
            
        if hasattr(self, 'lock_manager'):
            self.lock_manager.release_all_global()
            
        from nava.core.schemas import Event
        import uuid, datetime
        evt = Event(
            event_id=f"evt-halt-{uuid.uuid4().hex[:8]}",
            event_type="EMERGENCY_HALT",
            task_id=self.root_agent.budget_ref or "global",
            payload={"reason": reason, "timestamp": datetime.datetime.utcnow().isoformat()}
        )
        self.ledger.append_event(evt)
        print("[Orchestrator] Emergency halt executed. All systems safely secured.")




if __name__ == "__main__":
    if not os.path.exists("nava.yaml"):
        # Write a dummy config for manual testing
        with open("nava.yaml", "w") as f:
            f.write("""
root_agent:
  ceiling_permissions:
    - filesystem.write
    - filesystem.read
    - data.analyze
    - test.run
  ceiling_tools:
    - file.write
    - file.create_pdf
    - file.create_docx
    - file.create_pptx
    - file.read
    - test.run
budget:
  max_agents: 50
  max_depth: 10
  max_steps: 1000
  max_tokens: 1000000
""")
    
    import sys
    orch = Orchestrator()
    if len(sys.argv) > 1:
        objective = " ".join(sys.argv[1:])
    else:
        objective = input("Enter objective: ")
        
    if objective:
        orch.run(objective)
