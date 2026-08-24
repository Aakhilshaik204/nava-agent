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
        default_yaml = """# NAVA Personal Agent OS Configuration & Security Ceilings
root_agent:
  ceiling_permissions:
    - filesystem.write
    - filesystem.read
    - data.analyze
    - test.run
    - terminal.execute
    - shell.execute
    - gmail.read
    - gmail.search
    - gmail.draft
    - browser.navigate
    - browser.read
    - browser.click
    - browser.type
    - browser.scroll
    - browser.save_to_scratch
    - search.web
    - desktop.read
    - desktop.click
    - desktop.type
    - system.read_skill
    - system.flag_review
    - memory.semantic
    - mock.send_wire_transfer
    - mock.notify_admin

  ceiling_tools:
    - file.read
    - file.write
    - file.delete
    - file.create_pdf
    - file.create_docx
    - file.create_pptx
    - code.search
    - code.read_directory_tree
    - code.diff_review
    - code.replace_content
    - code.replace_content_batch
    - code.find_references
    - shell.execute
    - terminal.execute
    - test.run
    - git.status
    - git.diff
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
    - desktop.screenshot
    - desktop.click
    - desktop.type
    - desktop.hotkey
    - desktop.get_screen_size
    - gmail.search
    - gmail.read
    - system.read_skill
    - system.flag_review
    - mock.send_wire_transfer
    - mock.notify_admin

  ceiling_credentials:
    - gmail.read

budget:
  max_agents: 50
  max_depth: 10
  max_steps: 1000
  max_tokens: 1000000

security_switches:
  enable_terminal_execution: true
  enable_desktop_gui_control: true
  enable_external_integrations: true
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
        ceiling_permissions = root_config.get("ceiling_permissions", [])
        ceiling_tools = root_config.get("ceiling_tools", [])
        ceiling_credentials = root_config.get("ceiling_credentials", [])

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
