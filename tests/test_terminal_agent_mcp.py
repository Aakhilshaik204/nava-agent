import unittest
import os
import shutil
import tempfile
from datetime import datetime, timedelta

from nava.tools.registry import ToolRegistry
from nava.tools.tool_manifest import get_default_tools
from nava.tools.executor import LocalToolExecutor
from nava.core.schemas import ToolRequest, AgentState, AgentSpec, AgentType, Priority
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.agents.factory import AgentFactory
from nava.agents.templates import Templates, StaticAgentTemplate

class TestTerminalAgentMCP(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.registry = ToolRegistry()
        for tool_def in get_default_tools():
            self.registry.register_tool(tool_def)
            
        self.executor = LocalToolExecutor(registry=self.registry)
        self.executor.set_active_project("TestDevOpsProject")
        
        self.policy_engine = DefaultPolicyEngine()
        self.budget_engine = DefaultBudgetEngine()
        self.factory = AgentFactory(self.registry, self.policy_engine, self.budget_engine)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_terminal_exec_command(self):
        req = ToolRequest(
            request_id="req-term-1",
            agent_id="agt-term-1",
            tool_name="terminal.exec_command",
            arguments={"command": 'python -c "print(\'NAVA_DEVOPS_OK\')"', "timeout": 10},
            requested_scope="terminal.execute"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        self.assertEqual(res.get("returncode"), 0)
        self.assertIn("NAVA_DEVOPS_OK", res.get("stdout", ""))
        self.assertGreaterEqual(res.get("duration_seconds", 0), 0)

    def test_terminal_timeout_enforcement(self):
        # Command that sleeps longer than timeout
        req = ToolRequest(
            request_id="req-term-2",
            agent_id="agt-term-1",
            tool_name="terminal.exec_command",
            arguments={"command": 'python -c "import time; time.sleep(5)"', "timeout": 1},
            requested_scope="terminal.execute"
        )
        res = self.executor.execute(req)
        self.assertFalse(res.get("success", True))
        self.assertTrue(res.get("timed_out", False))
        self.assertIn("timed out", res.get("error", "").lower())

    def test_terminal_secret_redaction(self):
        # Command that echoes simulated API tokens
        req = ToolRequest(
            request_id="req-term-3",
            agent_id="agt-term-1",
            tool_name="terminal.exec_command",
            arguments={"command": 'python -c "print(\'api_key=ghp_ABC12345678901234567890\')"', "timeout": 10},
            requested_scope="terminal.execute"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        stdout = res.get("stdout", "")
        self.assertNotIn("ghp_ABC12345678901234567890", stdout)
        self.assertIn("[REDACTED", stdout)

    def test_terminal_run_tests(self):
        # 1. Create a sample passing test file inside temp workspace
        test_file = os.path.join(self.test_dir, "test_sample_service.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                "import unittest\n"
                "class SampleTestCase(unittest.TestCase):\n"
                "    def test_math(self):\n"
                "        self.assertEqual(1 + 1, 2)\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n"
            )

        req = ToolRequest(
            request_id="req-term-4",
            agent_id="agt-term-1",
            tool_name="terminal.run_tests",
            arguments={"test_command": f"python {test_file}", "framework": "unittest"},
            requested_scope="test.run"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        self.assertEqual(res.get("verdict"), "PASSED")
        self.assertEqual(res.get("passed"), 1)
        self.assertEqual(res.get("failed"), 0)

    def test_terminal_inspect_environment(self):
        req = ToolRequest(
            request_id="req-term-5",
            agent_id="agt-term-1",
            tool_name="terminal.inspect_environment",
            arguments={},
            requested_scope="system.inspect"
        )
        res = self.executor.execute(req)
        self.assertIn("os", res)
        self.assertIn("python", res.get("installed_toolchains", {}))
        self.assertIn("installed_toolchains", res)

    def test_docker_sandbox_lifecycle(self):
        # 1. Create Sandbox
        req_create = ToolRequest(
            request_id="req-dock-1",
            agent_id="agt-term-1",
            tool_name="docker.create_sandbox",
            arguments={"image": "python:3.11-slim", "memory_limit": "256m"},
            requested_scope="docker.sandbox"
        )
        res_create = self.executor.execute(req_create)
        self.assertTrue(res_create.get("success", False))
        sandbox_id = res_create.get("sandbox_id")
        self.assertIsNotNone(sandbox_id)

        # 2. Exec in Sandbox
        req_exec = ToolRequest(
            request_id="req-dock-2",
            agent_id="agt-term-1",
            tool_name="docker.exec_in_sandbox",
            arguments={"sandbox_id": sandbox_id, "command": 'python -c "print(42*2)"', "timeout": 10},
            requested_scope="docker.sandbox"
        )
        res_exec = self.executor.execute(req_exec)
        self.assertTrue(res_exec.get("success", False))
        self.assertIn("84", res_exec.get("stdout", ""))

        # 3. Destroy Sandbox
        req_destroy = ToolRequest(
            request_id="req-dock-3",
            agent_id="agt-term-1",
            tool_name="docker.destroy_sandbox",
            arguments={"sandbox_id": sandbox_id},
            requested_scope="docker.sandbox"
        )
        res_destroy = self.executor.execute(req_destroy)
        self.assertTrue(res_destroy.get("success", False))

    def test_role_restrictions_enforcement(self):
        parent_state = AgentState(
            agent_id="agt-root",
            role="RootAgent",
            type=AgentType.STATIC,
            goal="DevOps root",
            permission_scope=["*"],
            credential_scope=["*"],
            tool_scope=["*"],
            depth=0,
            ttl=timedelta(minutes=10),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            budget_ref="bgt-1"
        )

        # 1. TerminalAgent requesting docker.create_sandbox & terminal.exec_command -> MUST SUCCEED
        spec_term = AgentSpec(
            request_id="spec-term-1",
            requested_role="TerminalAgent",
            goal="Run build and tests in container",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["terminal.execute", "docker.sandbox", "test.run", "system.inspect"],
            requested_tools=["terminal.exec_command", "docker.create_sandbox", "terminal.run_tests"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-term-1"
        )
        agent_term = self.factory.spawn_agent(spec_term, parent_state)
        self.assertIn("terminal.exec_command", agent_term.tool_scope)
        self.assertIn("docker.create_sandbox", agent_term.tool_scope)
        self.assertIn("terminal.run_tests", agent_term.tool_scope)

        # 2. DocumentAgent requesting docker.create_sandbox -> MUST BE STRIPPED
        spec_doc = AgentSpec(
            request_id="spec-doc-1",
            requested_role="DocumentAgent",
            goal="Compile PDF document",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["document.compile", "docker.sandbox"],
            requested_tools=["typst.compile_pdf", "docker.create_sandbox"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-doc-1"
        )
        agent_doc = self.factory.spawn_agent(spec_doc, parent_state)
        self.assertNotIn("docker.create_sandbox", agent_doc.tool_scope)

if __name__ == "__main__":
    unittest.main()
