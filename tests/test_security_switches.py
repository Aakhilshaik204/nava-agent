import unittest
import os
import shutil
import tempfile
import yaml

from nava.core.boot import Bootstrapper
from nava.core.schemas import AgentStatus

class TestSecuritySwitches(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, "nava.yaml")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_security_switches_all_enabled(self):
        # Default bootstrap
        boot = Bootstrapper(self.config_path)
        root, budget = boot.bootstrap()
        self.assertEqual(root.status, AgentStatus.RUNNING)
        self.assertIn("terminal.execute", root.permission_scope)
        self.assertIn("docker.create_sandbox", root.tool_scope)
        self.assertIn("desktop.click", root.tool_scope)
        self.assertIn("browser.navigate", root.tool_scope)
        self.assertIn("gmail.search", root.tool_scope)

    def test_disable_terminal_and_docker(self):
        # Write config with terminal and docker disabled
        custom_yaml = """
root_agent:
  ceiling_permissions: ["terminal.execute", "shell.execute", "docker.sandbox", "filesystem.read"]
  ceiling_tools: ["terminal.execute", "shell.execute", "terminal.exec_command", "docker.create_sandbox", "file.read"]
  ceiling_credentials: []
budget:
  max_agents: 10
security_switches:
  enable_terminal_execution: false
  enable_docker_sandboxing: false
"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(custom_yaml)

        boot = Bootstrapper(self.config_path)
        root, _ = boot.bootstrap()
        self.assertNotIn("terminal.execute", root.permission_scope)
        self.assertNotIn("docker.sandbox", root.permission_scope)
        self.assertNotIn("terminal.exec_command", root.tool_scope)
        self.assertNotIn("docker.create_sandbox", root.tool_scope)
        self.assertIn("file.read", root.tool_scope)

    def test_disable_desktop_gui_control(self):
        # Write config making ComputerAgent read-only
        custom_yaml = """
root_agent:
  ceiling_permissions: ["desktop.read", "desktop.click", "desktop.type"]
  ceiling_tools: ["desktop.screenshot", "desktop.get_screen_size", "desktop.click", "desktop.type", "desktop.hotkey"]
  ceiling_credentials: []
budget:
  max_agents: 10
security_switches:
  enable_desktop_gui_control: false
"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(custom_yaml)

        boot = Bootstrapper(self.config_path)
        root, _ = boot.bootstrap()
        self.assertNotIn("desktop.click", root.permission_scope)
        self.assertNotIn("desktop.type", root.permission_scope)
        self.assertNotIn("desktop.click", root.tool_scope)
        self.assertNotIn("desktop.type", root.tool_scope)
        self.assertNotIn("desktop.hotkey", root.tool_scope)
        # Read-only screenshot and resolution remain available
        self.assertIn("desktop.screenshot", root.tool_scope)
        self.assertIn("desktop.get_screen_size", root.tool_scope)

    def test_disable_external_integrations(self):
        custom_yaml = """
root_agent:
  ceiling_permissions: ["gmail.read", "github.read", "brave.search", "filesystem.read"]
  ceiling_tools: ["gmail.search", "github.clone", "brave.search_web", "file.read"]
  ceiling_credentials: ["gmail.read"]
budget:
  max_agents: 10
security_switches:
  enable_external_integrations: false
"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write(custom_yaml)

        boot = Bootstrapper(self.config_path)
        root, _ = boot.bootstrap()
        self.assertNotIn("gmail.read", root.permission_scope)
        self.assertNotIn("brave.search", root.permission_scope)
        self.assertNotIn("gmail.search", root.tool_scope)
        self.assertNotIn("brave.search_web", root.tool_scope)
        self.assertEqual(root.credential_scope, [])
        self.assertIn("file.read", root.tool_scope)

    def test_disable_specific_mcp_server(self):
        from nava.tools.registry import ToolRegistry
        from nava.tools.mcp_client import MCPClientManager
        from nava.tools.tool_manifest import register_default_mcp_servers
        
        registry = ToolRegistry()
        mcp_mgr = MCPClientManager(registry=registry, ledger_path=os.path.join(self.test_dir, "mcp_ledger.json"))
        configs = {
            "context7": {"enabled": False},
            "superpowers": {"enabled": True},
            "sqlite": {"enabled": False}
        }
        register_default_mcp_servers(mcp_mgr, mcp_configs=configs)
        
        # context7 and sqlite should not be registered
        self.assertNotIn("context7", mcp_mgr.servers)
        self.assertNotIn("sqlite", mcp_mgr.servers)
        # superpowers should be registered
        self.assertIn("superpowers", mcp_mgr.servers)

    def test_executor_blocks_disabled_tool(self):
        from nava.tools.registry import ToolRegistry
        from nava.tools.executor import LocalToolExecutor
        from nava.core.schemas import ToolRequest

        registry = ToolRegistry()
        # Do not register arxiv
        executor = LocalToolExecutor(registry=registry)
        req = ToolRequest(
            request_id="req-1",
            agent_id="agt-1",
            tool_name="arxiv.search_papers",
            arguments={"query": "quantum"},
            requested_scope="research.read"
        )
        res = executor.execute(req)
        self.assertFalse(res.get("success", True))
        self.assertIn("DISABLED_TOOL", res.get("error", ""))

    def test_task_artifact_routing_in_file_write(self):
        from nava.tools.registry import ToolRegistry
        from nava.tools.tool_manifest import get_default_tools
        from nava.tools.executor import LocalToolExecutor
        from nava.core.schemas import ToolRequest

        registry = ToolRegistry()
        for t in get_default_tools():
            registry.register_tool(t)
        executor = LocalToolExecutor(registry=registry)
        executor.set_active_task("tsk_test_routing_123")

        # Write generic tasks/summary.md
        req = ToolRequest(
            request_id="req-2",
            agent_id="agt-1",
            tool_name="file.write",
            arguments={"filename": "tasks/summary.md", "content": "# Test Summary"},
            requested_scope="filesystem.write"
        )
        res = executor.execute(req)
        self.assertTrue(res.get("success", False))
        saved_to = res.get("saved_to", "").replace("\\", "/")
        self.assertIn("tasks/tsk_test_routing_123/artifacts/summary.md", saved_to)

if __name__ == "__main__":
    unittest.main()
