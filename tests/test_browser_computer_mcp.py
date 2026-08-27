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

class TestBrowserComputerMCP(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.registry = ToolRegistry()
        for tool_def in get_default_tools():
            self.registry.register_tool(tool_def)
            
        self.executor = LocalToolExecutor(registry=self.registry)
        self.executor.set_active_task("tsk_test_browser_computer")
        self.executor.set_active_project("TestWebProject")
        
        self.policy_engine = DefaultPolicyEngine()
        self.budget_engine = DefaultBudgetEngine()
        self.factory = AgentFactory(self.registry, self.policy_engine, self.budget_engine)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)
        # Teardown any browser sessions
        if hasattr(self.executor, '_thread_local') and getattr(self.executor._thread_local, 'browser_engine', None):
            try:
                self.executor._thread_local.browser_engine.close()
            except Exception:
                pass

    def test_browser_navigate_and_tree(self):
        # 1. Navigate
        req_nav = ToolRequest(
            request_id="req-b-1",
            agent_id="agt-b-1",
            tool_name="browser.navigate",
            arguments={"url": "https://example.com"},
            requested_scope="browser.navigate"
        )
        res_nav = self.executor.execute(req_nav)
        self.assertTrue(res_nav.get("success", False))

        # 2. Extract Interactive Tree
        req_tree = ToolRequest(
            request_id="req-b-2",
            agent_id="agt-b-1",
            tool_name="browser.extract_interactive_tree",
            arguments={},
            requested_scope="browser.read"
        )
        res_tree = self.executor.execute(req_tree)
        self.assertTrue(res_tree.get("success", False))
        self.assertIn("interactive_tree", res_tree)
        self.assertIn("[#", res_tree.get("interactive_tree", ""))

    def test_browser_form_interaction(self):
        # 0. Navigate & Extract Interactive Tree
        self.executor.execute(ToolRequest(
            request_id="req-b-nav-init",
            agent_id="agt-b-1",
            tool_name="browser.navigate",
            arguments={"url": "https://example.com"},
            requested_scope="browser.navigate"
        ))
        self.executor.execute(ToolRequest(
            request_id="req-b-tree-init",
            agent_id="agt-b-1",
            tool_name="browser.extract_interactive_tree",
            arguments={},
            requested_scope="browser.read"
        ))

        # 1. Type into element
        req_type = ToolRequest(
            request_id="req-b-3",
            agent_id="agt-b-1",
            tool_name="browser.type",
            arguments={"text": "NAVA Agent Search", "element_id": 1},
            requested_scope="browser.type"
        )
        res_type = self.executor.execute(req_type)
        self.assertTrue(res_type.get("success", False))

        # 2. Click element
        req_click = ToolRequest(
            request_id="req-b-4",
            agent_id="agt-b-1",
            tool_name="browser.click",
            arguments={"element_id": 1},
            requested_scope="browser.click"
        )
        res_click = self.executor.execute(req_click)
        self.assertTrue(res_click.get("success", False))

        # 3. Scroll
        req_scroll = ToolRequest(
            request_id="req-b-5",
            agent_id="agt-b-1",
            tool_name="browser.scroll",
            arguments={"direction": "down", "amount": 400},
            requested_scope="browser.scroll"
        )
        res_scroll = self.executor.execute(req_scroll)
        self.assertTrue(res_scroll.get("success", False))

    def test_browser_screenshot_to_artifact(self):
        req_shot = ToolRequest(
            request_id="req-b-6",
            agent_id="agt-b-1",
            tool_name="browser.screenshot",
            arguments={},
            requested_scope="browser.read"
        )
        res_shot = self.executor.execute(req_shot)
        self.assertTrue(res_shot.get("success", False))
        saved_to = res_shot.get("saved_to", "")
        self.assertTrue(os.path.exists(saved_to))

    def test_browser_security_blocks(self):
        # 1. Block SSRF / Local IP
        req_block_ip = ToolRequest(
            request_id="req-b-7",
            agent_id="agt-b-1",
            tool_name="browser.navigate",
            arguments={"url": "http://127.0.0.1:8080"},
            requested_scope="browser.navigate"
        )
        res_block_ip = self.executor.execute(req_block_ip)
        self.assertFalse(res_block_ip.get("success", True))
        self.assertIn("SECURITY_BLOCK", res_block_ip.get("error", ""))

        # 2. Block typing sensitive tokens
        req_block_token = ToolRequest(
            request_id="req-b-8",
            agent_id="agt-b-1",
            tool_name="browser.type",
            arguments={"text": "sk-123456789012345678901234", "element_id": 1},
            requested_scope="browser.type"
        )
        res_block_token = self.executor.execute(req_block_token)
        self.assertFalse(res_block_token.get("success", True))
        self.assertIn("SECURITY_BLOCK", res_block_token.get("error", ""))

    def test_desktop_screen_size_and_screenshot(self):
        # 1. Screen size
        req_size = ToolRequest(
            request_id="req-c-1",
            agent_id="agt-c-1",
            tool_name="desktop.get_screen_size",
            arguments={},
            requested_scope="desktop.read"
        )
        res_size = self.executor.execute(req_size)
        self.assertTrue(res_size.get("success", False))
        self.assertGreater(res_size.get("width", 0), 0)
        self.assertGreater(res_size.get("height", 0), 0)

        # 2. Screenshot
        req_shot = ToolRequest(
            request_id="req-c-2",
            agent_id="agt-c-1",
            tool_name="desktop.screenshot",
            arguments={"path": "desktop_screen_test.png"},
            requested_scope="desktop.read"
        )
        res_shot = self.executor.execute(req_shot)
        self.assertTrue(res_shot.get("success", False))
        saved_path = res_shot.get("saved_to")
        self.assertIsNotNone(saved_path)
        self.assertTrue(os.path.exists(saved_path))

    def test_desktop_mouse_and_keyboard(self):
        # 1. Click
        req_click = ToolRequest(
            request_id="req-c-3",
            agent_id="agt-c-1",
            tool_name="desktop.click",
            arguments={"x": 200, "y": 200, "button": "left"},
            requested_scope="desktop.click"
        )
        res_click = self.executor.execute(req_click)
        self.assertTrue(res_click.get("success", False))

        # 2. Type
        req_type = ToolRequest(
            request_id="req-c-4",
            agent_id="agt-c-1",
            tool_name="desktop.type",
            arguments={"text": "NAVA OS Testing", "interval": 0.01},
            requested_scope="desktop.type"
        )
        res_type = self.executor.execute(req_type)
        self.assertTrue(res_type.get("success", False))

        # 3. Hotkey
        req_hotkey = ToolRequest(
            request_id="req-c-5",
            agent_id="agt-c-1",
            tool_name="desktop.hotkey",
            arguments={"keys": ["ctrl", "c"]},
            requested_scope="desktop.type"
        )
        res_hotkey = self.executor.execute(req_hotkey)
        self.assertTrue(res_hotkey.get("success", False))

    def test_role_restrictions_enforcement(self):
        parent_state = AgentState(
            agent_id="agt-root",
            role="RootAgent",
            type=AgentType.STATIC,
            goal="Web & Desktop Automation Root",
            permission_scope=["*"],
            credential_scope=["*"],
            tool_scope=["*"],
            depth=0,
            ttl=timedelta(minutes=10),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            budget_ref="bgt-1"
        )

        # 1. BrowserAgent requesting browser.extract_interactive_tree & browser.click -> MUST SUCCEED
        spec_browser = AgentSpec(
            request_id="spec-b-1",
            requested_role="BrowserAgent",
            goal="Interact with web form",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["browser.read", "browser.click", "browser.type", "browser.navigate"],
            requested_tools=["browser.navigate", "browser.extract_interactive_tree", "browser.click", "browser.type"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-browser-1"
        )
        agent_browser = self.factory.spawn_agent(spec_browser, parent_state)
        self.assertIn("browser.navigate", agent_browser.tool_scope)
        self.assertIn("browser.extract_interactive_tree", agent_browser.tool_scope)
        self.assertIn("browser.click", agent_browser.tool_scope)

        # 2. ComputerAgent requesting desktop.click & desktop.screenshot -> MUST SUCCEED
        spec_comp = AgentSpec(
            request_id="spec-c-1",
            requested_role="ComputerAgent",
            goal="Automate desktop GUI",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["desktop.read", "desktop.click", "desktop.type"],
            requested_tools=["desktop.screenshot", "desktop.click", "desktop.type", "desktop.get_screen_size"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-comp-1"
        )
        agent_comp = self.factory.spawn_agent(spec_comp, parent_state)
        self.assertIn("desktop.screenshot", agent_comp.tool_scope)
        self.assertIn("desktop.click", agent_comp.tool_scope)

        # 3. CodingAgent requesting desktop.click -> MUST BE STRIPPED
        spec_coding = AgentSpec(
            request_id="spec-code-1",
            requested_role="CodingAgent",
            goal="Write Python script",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["filesystem.write", "desktop.click"],
            requested_tools=["file.write", "desktop.click"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-code-1"
        )
        agent_coding = self.factory.spawn_agent(spec_coding, parent_state)
        self.assertNotIn("desktop.click", agent_coding.tool_scope)

if __name__ == "__main__":
    unittest.main()
