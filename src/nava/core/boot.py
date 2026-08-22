import os
import uuid
import datetime
from typing import List, Dict, Any
import yaml
from nava.core.schemas import AgentState, AgentType, AgentStatus, TaskBudget

class NavaBootstrapper:
    """
    Bootstraps the root agent and global task budget from a configuration file.
    """
    def __init__(self, config_path: str = "nava.yaml"):
        self.config_path = config_path

    def bootstrap(self) -> (AgentState, TaskBudget):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Configuration file {self.config_path} not found.")

        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        if not config:
            raise ValueError("Configuration file is empty.")

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
