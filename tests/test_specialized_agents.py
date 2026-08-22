import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from nava.tools.desktop import DesktopEngine
from nava.agents.templates import Templates
from nava.tools.registry import ToolRegistry, ToolDefinition, RiskTier
from nava.tools.executor import LocalToolExecutor
from nava.core.schemas import ToolRequest, AgentState
from nava.governance.risk_engine import DefaultRiskEngine
from nava.memory.store import ProfileMemoryStore

class TestSpecializedAgents(unittest.TestCase):
    def setUp(self):
        self.desktop = DesktopEngine()

    def test_desktop_screen_size_and_dpi(self):
        """Verify get_screen_size returns valid dimensions and DPI scale."""
        size = self.desktop.get_screen_size()
        self.assertIn("width", size)
        self.assertIn("height", size)
        self.assertIn("dpi_scale", size)
        self.assertGreater(size["width"], 0)
        self.assertGreater(size["height"], 0)

    def test_desktop_screenshot_full_and_cropped(self):
        """Verify full and region-cropped screenshots generate valid image files."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Full screenshot
            saved_path = self.desktop.screenshot(tmp_path)
            self.assertTrue(os.path.exists(saved_path))
            self.assertGreater(os.path.getsize(saved_path), 0)

            # Cropped region screenshot
            region = {"left": 0, "top": 0, "width": 200, "height": 200}
            cropped_path = self.desktop.screenshot(tmp_path, region=region)
            self.assertTrue(os.path.exists(cropped_path))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_desktop_mouse_and_keyboard_controls(self):
        """Verify simulated mouse drag, scroll, and key press."""
        res_drag = self.desktop.mouse_drag(100, 100, 200, 200)
        self.assertTrue("Dragged" in res_drag or "Simulated" in res_drag)

        res_scroll = self.desktop.mouse_scroll(-5)
        self.assertTrue("Scrolled" in res_scroll)

        res_press = self.desktop.keyboard_press("enter")
        self.assertTrue("Pressed" in res_press)

    def test_desktop_sensitive_typing_blocked(self):
        """Verify DesktopEngine refuses to type sensitive API keys or tokens."""
        res1 = self.desktop.type_text("sk-123456789012345678901234567890")
        self.assertIn("SECURITY_BLOCK", res1)

        res2 = self.desktop.type_text("ya29.a0AfH6SMD_random_token_here")
        self.assertIn("SECURITY_BLOCK", res2)

    def test_desktop_high_risk_triggers_hitl(self):
        """Verify high-risk desktop GUI actions trigger HITL in RiskEngine."""
        from datetime import datetime, timedelta
        from nava.core.schemas import AgentType
        profile_store = ProfileMemoryStore()
        risk_engine = DefaultRiskEngine(profile_store)
        
        now = datetime.utcnow()
        req = ToolRequest(
            request_id="req-desktop-delete",
            agent_id="agt-comp-1",
            tool_name="desktop.type",
            arguments={"text": "delete all database records now"},
            requested_scope="desktop.type",
            created_at=now
        )
        agent_state = AgentState(
            agent_id="agt-comp-1",
            role="ComputerAgent",
            type=AgentType.STATIC,
            goal="Clean database",
            parent_agent_id="root",
            tool_scope=["desktop.type"],
            permission_scope=["desktop.type"],
            credential_scope=[],
            created_at=now,
            ttl=timedelta(seconds=300),
            expires_at=now + timedelta(seconds=300),
            depth=1,
            budget_ref="root_budget"
        )
        
        assessment = risk_engine.evaluate(req, agent_state)
        self.assertGreaterEqual(assessment.total_score, 55)
        self.assertEqual(assessment.tier, RiskTier.HIGH)

    def test_templates_permissions(self):
        """Verify ComputerAgent, TerminalAgent, and ResearchAgent template definitions."""
        self.assertIn("desktop.*", Templates.ComputerAgent.permission_scope)
        self.assertIn("test.run", Templates.TerminalAgent.permission_scope)
        self.assertIn("terminal.execute", Templates.TerminalAgent.permission_scope)
        self.assertIn("browser.*", Templates.ResearchAgent.permission_scope)
        self.assertIn("filesystem.write", Templates.ResearchAgent.permission_scope)

    def test_executor_desktop_tool_dispatch(self):
        """Verify LocalToolExecutor dispatches desktop tools."""
        executor = LocalToolExecutor()
        req = ToolRequest(
            request_id="req-test-1",
            agent_id="agt-comp-1",
            tool_name="desktop.get_screen_size",
            arguments={},
            requested_scope="desktop.read"
        )
        res = executor.execute_tool(req)
        self.assertIn("width", res)
        self.assertIn("height", res)
        self.assertIn("dpi_scale", res)

    def test_research_and_terminal_tools_dispatch(self):
        """Verify ResearchAgent and TerminalAgent tools dispatch in LocalToolExecutor."""
        executor = LocalToolExecutor()

        # Test search.web
        req_search = ToolRequest(
            request_id="req-srch-1",
            agent_id="agt-res-1",
            tool_name="search.web",
            arguments={"query": "python"},
            requested_scope="search.web"
        )
        res_srch = executor.execute_tool(req_search)
        self.assertIn("query", res_srch)

        # Test memory.semantic_ingest
        req_mem = ToolRequest(
            request_id="req-mem-1",
            agent_id="agt-res-1",
            tool_name="memory.semantic_ingest",
            arguments={"content": "NAVA OS uses 4-tier memory.", "source": "test"},
            requested_scope="memory.semantic"
        )
        res_mem = executor.execute_tool(req_mem)
        self.assertTrue(res_mem.get("success"))

        # Test git.status
        req_git = ToolRequest(
            request_id="req-git-1",
            agent_id="agt-term-1",
            tool_name="git.status",
            arguments={},
            requested_scope="git.read"
        )
        res_git = executor.execute_tool(req_git)
        self.assertIn("branch", res_git)

    def test_security_switches_blocking(self):
        """Verify DefaultPolicyEngine blocks dangerous tools when switches are disabled."""
        from nava.governance.policy_engine import DefaultPolicyEngine
        from nava.core.schemas import Outcome, AgentState, AgentType
        from datetime import datetime, timedelta

        policy = DefaultPolicyEngine(security_switches={
            "enable_terminal_execution": False,
            "enable_desktop_gui_control": False,
            "enable_external_integrations": False
        })

        agent_state = AgentState(
            agent_id="agt-sec-1",
            role="TerminalAgent",
            type=AgentType.STATIC,
            goal="Test Security Switch",
            parent_agent_id="root",
            tool_scope=["terminal.execute"],
            permission_scope=["terminal.execute"],
            credential_scope=[],
            created_at=datetime.utcnow(),
            ttl=timedelta(seconds=60),
            expires_at=datetime.utcnow() + timedelta(seconds=60),
            depth=1,
            budget_ref="test_budget"
        )

        # Terminal execution must be blocked
        req_term = ToolRequest(
            request_id="req-blk-1",
            agent_id="agt-sec-1",
            tool_name="terminal.execute",
            arguments={"command": "dir"},
            requested_scope="terminal.execute"
        )
        outcome_term = policy.evaluate(req_term, agent_state)
        self.assertEqual(outcome_term, Outcome.BLOCK)

        # Desktop click must be blocked
        req_desk = ToolRequest(
            request_id="req-blk-2",
            agent_id="agt-sec-1",
            tool_name="desktop.click",
            arguments={"x": 100, "y": 100},
            requested_scope="desktop.click"
        )
        outcome_desk = policy.evaluate(req_desk, agent_state)
        self.assertEqual(outcome_desk, Outcome.BLOCK)

if __name__ == "__main__":
    unittest.main()
