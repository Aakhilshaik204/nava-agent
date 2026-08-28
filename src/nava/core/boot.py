import os
import uuid
import datetime
from typing import List, Dict, Any, Tuple
import yaml
from nava.core.schemas import AgentState, AgentType, AgentStatus, TaskBudget

class NavaBootstrapper:
    """
    Bootstraps the root agent and global task budget from a configuration file.
    Auto-creates default nava.yaml if not present.
    """
    def __init__(self, config_path: str = "nava.yaml"):
        self.config_path = config_path

    def _create_default_config(self) -> None:
        default_yaml = """# ==============================================================================
# NAVA Personal Agent OS Configuration & Root Security Ceilings (Blueprint Sec 26)
# ==============================================================================

root_agent:
  ceiling_permissions:
    # Filesystem & Storage
    - filesystem.write
    - filesystem.read
    - data.analyze
    
    # DevOps & Execution (shell.execute restricted EXCLUSIVELY to TerminalAgent)
    - test.run
    - terminal.execute
    - shell.execute
    - docker.sandbox
    - system.inspect
    - git.read
    - git.write
    - ast.read
    - ast.write
    
    # Model Context Protocol (MCP) & Integrations
    - gmail.read
    - gmail.search
    - gmail.draft
    
    # Research & Deep Intelligence MCP Suite
    - research.read
    - search.web
    
    # Data & Database MCP Suite (DataAgent)
    - database.read
    - database.write
    - data.analyze
    
    # Document & Typst PDF Compilation Suite (DocumentAgent & UniversalFileAgent)
    - document.compile
    - document.read
    
    # Web & Browser Automation
    - browser.navigate
    - browser.read
    - browser.click
    - browser.type
    - browser.scroll
    - browser.save_to_scratch
    
    # OS Desktop GUI Automation (ComputerAgent)
    - desktop.read
    - desktop.click
    - desktop.type
    
    # Skills, Knowledge & System
    - system.read_skill
    - system.flag_review
    - memory.semantic
    - reasoning.sequential
    - audit.verify
    - audit.security
    - mock.send_wire_transfer
    - mock.notify_admin

  ceiling_tools:
    # 1. File & Executive Document Tools
    - file.read
    - file.write
    - file.delete
    - file.create_pdf
    - file.create_docx
    - file.create_pptx
    
    # 2. Code, AST Indexing & Superpowers Tools
    - code.search
    - code.read_directory_tree
    - code.diff_review
    - code.replace_content
    - code.replace_content_batch
    - code.find_references
    - context7.get_symbol_graph
    - context7.slice_context
    - superpowers.ast_search
    - superpowers.ast_replace
    - superpowers.compiler_autofix
    
    # 3. Terminal & DevOps Tools (Restricted strictly to TerminalAgent & CodingAgent)
    - shell.execute
    - terminal.execute
    - terminal.exec_command
    - terminal.run_tests
    - terminal.inspect_environment
    - docker.create_sandbox
    - docker.exec_in_sandbox
    - docker.destroy_sandbox
    - test.run
    - git.status
    - git.diff
    - git.branch
    - git.commit
    
    # 4. Web & Research Tools (BrowserAgent & ResearchAgent)
    - browser.navigate
    - browser.extract_dom
    - browser.extract_text
    - browser.click
    - browser.type
    - browser.scroll
    - browser.go_back
    - browser.get_url
    - browser.save_to_scratch
    - search.web
    - memory.semantic_ingest
    - memory.semantic_search
    
    # 5. OS Desktop GUI Tools (ComputerAgent)
    - desktop.screenshot
    - desktop.click
    - desktop.type
    - desktop.hotkey
    - desktop.get_screen_size
    
    # 6. MCP Protocol & Integrations
    - gmail.search
    - gmail.read
    - fetch.get_markdown
    - brave.search_web
    - arxiv.search_papers
    - arxiv.get_paper_summary
    - sqlite.read_query
    - sqlite.write_query
    - sqlite.list_tables
    - sqlite.describe_tables
    - data.sql_query_csv
    - data.profile_dataset
    - data.aggregate
    - data.correlation_matrix
    - data.detect_anomalies
    - data.pivot_table
    - typst.compile_pdf
    - typst.render_template
    - doc.read_document
    - sequential_thinking.step
    - audit.verify_invariants
    - audit.security_scan
    - audit.verify_grounding
    
    # 7. System & Governance
    - system.read_skill
    - system.flag_review
    - mock.send_wire_transfer
    - mock.notify_admin

  ceiling_credentials:
    - gmail.read

# Global Execution & Resource Budgets (Blueprint Sec 14)
budget:
  max_agents: 50
  max_depth: 10
  max_steps: 1000
  max_tokens: 1000000

# User-Configurable Security Feature Switches (Section 13 & 26)
security_switches:
  enable_terminal_execution: true    # Set to false to disable all local shell/terminal command execution
  enable_docker_sandboxing: true     # Set to false to disable ephemeral Docker container creation
  enable_desktop_gui_control: true   # Set to false to make ComputerAgent read-only (screenshots only, mouse/keyboard blocked)
  enable_browser_automation: true    # Set to false to disable Playwright web navigation & form automation
  enable_code_mutation: true         # Set to false to make CodingAgent read-only (AST replace/file writes blocked)
  enable_external_integrations: true # Set to false to block external web MCPs, Gmail, and GitHub integrations
  enable_deep_audit_gates: true      # Set to false to bypass sequential thinking and AST security scanners
  enforce_codebase_isolation: true   # Set to false to disable strict isolation of NAVA's internal framework files

# Model Context Protocol (MCP) Ecosystem & Specialized Agent Servers
# (Set enabled: false on any server to completely disable and unregister it)
mcp_servers:
  context7:
    enabled: true
    command: "npx"
    args: ["-y", "@context7/mcp-server@latest"]
    assigned_roles: ["CodingAgent"]
    trust_state: "TRUSTED"
  
  superpowers:
    enabled: true
    command: "uvx"
    args: ["mcp-superpowers-code@latest"]
    assigned_roles: ["CodingAgent"]
    trust_state: "TRUSTED"

  git:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-git@latest"]
    assigned_roles: ["CodingAgent", "TerminalAgent"]
    trust_state: "TRUSTED"

  fetch:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-fetch@latest"]
    assigned_roles: ["ResearchAgent"]
    trust_state: "TRUSTED"

  brave-search:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-brave-search@latest"]
    assigned_roles: ["ResearchAgent"]
    trust_state: "TRUSTED"

  arxiv:
    enabled: true
    command: "uvx"
    args: ["mcp-server-arxiv@latest"]
    assigned_roles: ["ResearchAgent"]
    trust_state: "TRUSTED"

  sqlite:
    enabled: true
    command: "uvx"
    args: ["mcp-server-sqlite@latest"]
    assigned_roles: ["DataAgent"]
    trust_state: "TRUSTED"

  typst:
    enabled: true
    command: "uvx"
    args: ["typst-mcp-server@latest"]
    assigned_roles: ["DocumentAgent", "UniversalFileAgent"]
    trust_state: "TRUSTED"

  sequential-thinking:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-sequential-thinking@latest"]
    assigned_roles: ["ReviewerAgent", "VerifierAgent"]
    trust_state: "TRUSTED"

  audit-scanner:
    enabled: true
    command: "uvx"
    args: ["nava-audit-mcp@latest"]
    assigned_roles: ["ReviewerAgent", "VerifierAgent"]
    trust_state: "TRUSTED"

  docker-sandbox:
    enabled: true
    command: "uvx"
    args: ["docker-sandbox-mcp@latest"]
    assigned_roles: ["TerminalAgent"]
    trust_state: "TRUSTED"

  playwright-browser:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-puppeteer@latest"]
    assigned_roles: ["BrowserAgent"]
    trust_state: "TRUSTED"

  desktop-automation:
    enabled: true
    command: "uvx"
    args: ["desktop-automation-mcp@latest"]
    assigned_roles: ["ComputerAgent"]
    trust_state: "TRUSTED"

  gmail:
    enabled: true
    command: "uvx"
    args: ["gmail-mcp-server@latest"]
    assigned_roles: ["EmailAgent"]
    trust_state: "TRUSTED"

  github:
    enabled: true
    command: "npx"
    args: ["-y", "@modelcontextprotocol/server-github@latest"]
    assigned_roles: ["GitHubAgent"]
    trust_state: "TRUSTED"
"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(default_yaml)

    def bootstrap(self) -> Tuple[AgentState, TaskBudget]:
        if not os.path.exists(self.config_path):
            self._create_default_config()

        with open(self.config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            self._create_default_config()
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

        root_config = config.get("root_agent", {})
        ceiling_permissions = list(root_config.get("ceiling_permissions", []))
        ceiling_tools = list(root_config.get("ceiling_tools", []))
        ceiling_credentials = list(root_config.get("ceiling_credentials", []))

        # Enforce User-Configurable Security Switches (Section 13 & 26)
        switches = config.get("security_switches", {})
        
        # 1. Terminal Execution Switch
        if not switches.get("enable_terminal_execution", True):
            ceiling_permissions = [p for p in ceiling_permissions if p not in ["terminal.execute", "shell.execute"]]
            ceiling_tools = [t for t in ceiling_tools if t not in ["terminal.execute", "shell.execute", "terminal.exec_command", "terminal.run_tests"]]

        # 2. Docker Sandboxing Switch
        if not switches.get("enable_docker_sandboxing", True):
            ceiling_permissions = [p for p in ceiling_permissions if p not in ["docker.sandbox"]]
            ceiling_tools = [t for t in ceiling_tools if not t.startswith("docker.")]

        # 3. Desktop GUI Control Switch (Make read-only: screenshot & resolution only)
        if not switches.get("enable_desktop_gui_control", True):
            ceiling_permissions = [p for p in ceiling_permissions if p not in ["desktop.click", "desktop.type"]]
            ceiling_tools = [t for t in ceiling_tools if t not in ["desktop.click", "desktop.type", "desktop.hotkey", "desktop.drag", "desktop.press"]]

        # 4. Browser Automation Switch
        if not switches.get("enable_browser_automation", True):
            ceiling_permissions = [p for p in ceiling_permissions if p not in ["browser.click", "browser.type", "browser.navigate", "browser.scroll"]]
            ceiling_tools = [t for t in ceiling_tools if t in ["browser.extract_text", "browser.extract_dom"] or not t.startswith("browser.")]

        # 5. External Integrations Switch (Gmail, GitHub, Brave, ArXiv, Fetch)
        if not switches.get("enable_external_integrations", True):
            ceiling_permissions = [p for p in ceiling_permissions if not p.startswith(("gmail.", "github.", "brave.", "arxiv.", "fetch."))]
            ceiling_tools = [t for t in ceiling_tools if not t.startswith(("gmail.", "github.", "brave.", "arxiv.", "fetch."))]
            ceiling_credentials = []

        # 6. Deep Audit Gates Switch
        if not switches.get("enable_deep_audit_gates", True):
            ceiling_permissions = [p for p in ceiling_permissions if p not in ["reasoning.sequential", "audit.security", "audit.verify"]]
            ceiling_tools = [t for t in ceiling_tools if not t.startswith(("sequential_thinking.", "audit."))]

        # 7. Individual MCP Server Toggles (mcp_servers.<name>.enabled: false)
        mcp_servers_cfg = config.get("mcp_servers", {})
        for srv_name, srv_data in mcp_servers_cfg.items():
            if isinstance(srv_data, dict) and not srv_data.get("enabled", True):
                if srv_name == "sqlite":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("sqlite.")]
                    ceiling_permissions = [p for p in ceiling_permissions if p not in ["database.read", "database.write"]]
                elif srv_name == "arxiv":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("arxiv.")]
                elif srv_name == "brave-search":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("brave.")]
                elif srv_name == "fetch":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("fetch.")]
                elif srv_name == "typst":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("typst.")]
                elif srv_name == "sequential-thinking":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("sequential_thinking.")]
                elif srv_name == "audit-scanner":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("audit.")]
                elif srv_name == "docker-sandbox":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("docker.")]
                elif srv_name == "desktop-automation":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("desktop.")]
                elif srv_name == "gmail":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("gmail.")]
                    ceiling_credentials = [c for c in ceiling_credentials if not c.startswith("gmail.")]
                elif srv_name == "github":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("github.")]
                elif srv_name == "context7":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("context7.")]
                elif srv_name == "superpowers":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("superpowers.")]
                elif srv_name == "git":
                    ceiling_tools = [t for t in ceiling_tools if not t.startswith("git.")]

        budget_config = config.get("budget", {})
        max_agents = budget_config.get("max_agents", 50)
        max_depth = budget_config.get("max_depth", 10)
        max_steps = budget_config.get("max_steps", 1000)
        max_tokens = budget_config.get("max_tokens", 1000000)

        task_id = f"task-{uuid.uuid4().hex[:8]}"

        budget = TaskBudget(
            task_id=task_id,
            max_agents=max_agents,
            max_depth=max_depth,
            max_steps=max_steps,
            max_tokens=max_tokens,
            max_runtime=datetime.timedelta(hours=2),
            max_retries=3
        )

        root_agent = AgentState(
            agent_id="system-root",
            role="Nava",
            type=AgentType.STATIC,
            goal="Orchestrate and achieve user objective.",
            permission_scope=ceiling_permissions,
            credential_scope=ceiling_credentials,
            tool_scope=ceiling_tools,
            depth=0,
            status=AgentStatus.RUNNING,
            ttl=datetime.timedelta(hours=24),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=24),
            budget_ref=task_id
        )

        return root_agent, budget

Bootstrapper = NavaBootstrapper
