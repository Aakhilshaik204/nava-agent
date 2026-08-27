import os
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta
from nava.tools.executor import LocalToolExecutor
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.core.schemas import ToolRequest, RiskTier, AgentSpec, AgentState, AgentType, Priority
from nava.agents.factory import AgentFactory
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine

class TestResearchAgentMCP(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        self.executor = LocalToolExecutor()
        self.executor.set_active_task("tsk_test_research")
        
        self.registry = ToolRegistry()
        self.registry.register_tool(ToolDefinition(
            name="fetch.get_markdown",
            description="Fetches URL to Markdown",
            input_schema={"url": "string"},
            output_schema={},
            permissions_required=["research.read"],
            risk_level=RiskTier.LOW,
            reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="brave.search_web",
            description="Searches web",
            input_schema={"query": "string"},
            output_schema={},
            permissions_required=["research.read"],
            risk_level=RiskTier.LOW,
            reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="arxiv.search_papers",
            description="Searches ArXiv",
            input_schema={"query": "string"},
            output_schema={},
            permissions_required=["research.read"],
            risk_level=RiskTier.LOW,
            reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="file.write",
            description="Writes file",
            input_schema={"filename": "string", "content": "string"},
            output_schema={},
            permissions_required=["filesystem.write"],
            risk_level=RiskTier.LOW,
            reversible=True
        ))
        
        self.policy_engine = DefaultPolicyEngine()
        self.budget_engine = DefaultBudgetEngine()
        self.factory = AgentFactory(self.registry, self.policy_engine, self.budget_engine)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_fetch_get_markdown(self):
        req = ToolRequest(
            request_id="req-fetch-1",
            agent_id="agt-research",
            tool_name="fetch.get_markdown",
            arguments={"url": "https://example.com"},
            requested_scope="research.read"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False) or "markdown" in res)
        if res.get("success"):
            self.assertIn("Example Domain", res.get("markdown", ""))
            self.assertIn("token_optimization", res)

    def test_brave_search_web(self):
        req = ToolRequest(
            request_id="req-brave-1",
            agent_id="agt-research",
            tool_name="brave.search_web",
            arguments={"query": "Model Context Protocol specifications", "count": 3},
            requested_scope="research.read"
        )
        res = self.executor.execute(req)
        self.assertIn("results", res)
        self.assertGreaterEqual(len(res["results"]), 1)
        self.assertIn("title", res["results"][0])
        self.assertIn("url", res["results"][0])

    def test_fetch_get_raw_html(self):
        req = ToolRequest(
            request_id="req-raw-1",
            agent_id="agt-research",
            tool_name="fetch.get_raw_html",
            arguments={"url": "https://example.com"},
            requested_scope="research.read"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False) or "raw_html" in res)

    def test_fetch_get_headers(self):
        req = ToolRequest(
            request_id="req-head-1",
            agent_id="agt-research",
            tool_name="fetch.get_headers",
            arguments={"url": "https://example.com"},
            requested_scope="research.read"
        )
        res = self.executor.execute(req)
        self.assertTrue("status_code" in res or "headers" in res)

    def test_brave_search_news(self):
        req = ToolRequest(
            request_id="req-news-1",
            agent_id="agt-research",
            tool_name="brave.search_news",
            arguments={"query": "Artificial Intelligence", "count": 2},
            requested_scope="research.read"
        )
        res = self.executor.execute(req)
        self.assertIn("results", res)

    def test_arxiv_search_papers(self):
        req = ToolRequest(
            request_id="req-arxiv-1",
            agent_id="agt-research",
            tool_name="arxiv.search_papers",
            arguments={"query": "transformer neural networks", "max_results": 2},
            requested_scope="research.read"
        )
        res = self.executor.execute(req)
        self.assertIn("papers", res)
        self.assertIsInstance(res["papers"], list)

    def test_role_restriction_blocks_non_research_agents(self):
        # Create a parent state with ceiling permissions
        parent_state = AgentState(
            agent_id="agt-root",
            role="RootAgent",
            type=AgentType.STATIC,
            goal="Manage system",
            permission_scope=["*"],
            credential_scope=["*"],
            tool_scope=["*"],
            depth=0,
            ttl=timedelta(minutes=10),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            budget_ref="bgt-1"
        )
        
        # 1. Spawn ResearchAgent with fetch.get_markdown -> MUST SUCCEED
        spec_research = AgentSpec(
            request_id="spec-1",
            requested_role="ResearchAgent",
            goal="Research AI specs",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["research.read", "fetch.*"],
            requested_tools=["fetch.get_markdown", "brave.search_web"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-1"
        )
        agent_research = self.factory.spawn_agent(spec_research, parent_state)
        self.assertIn("fetch.get_markdown", agent_research.tool_scope)
        self.assertIn("brave.search_web", agent_research.tool_scope)
        
        # 2. Attempt to spawn CodingAgent with fetch.get_markdown -> MUST BE STRIPPED
        spec_coding = AgentSpec(
            request_id="spec-2",
            requested_role="CodingAgent",
            goal="Write python code",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["filesystem.read", "filesystem.write", "research.read"],
            requested_tools=["fetch.get_markdown", "file.write"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-2"
        )
        agent_coding = self.factory.spawn_agent(spec_coding, parent_state)
        self.assertNotIn("fetch.get_markdown", agent_coding.tool_scope)

if __name__ == "__main__":
    unittest.main()
