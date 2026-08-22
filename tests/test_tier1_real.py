import pytest
import datetime
import os
import tempfile
from nava.core.schemas import AgentSpec, AgentState, AgentType, Outcome, RiskTier, AgentStatus, PolicyRule
from nava.agents.factory import AgentFactory
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.governance.risk_engine import DefaultRiskEngine
from nava.governance.hitl_manager import SingleApprovalManager
from nava.core.ledger import JsonlAuditLedger
from nava.agents.runtime.universal_file_graph import build_universal_file_graph
from nava.tools.executor import LocalToolExecutor

def test_tier1_real_execution():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = os.path.join(tmpdir, "audit.jsonl")
        ledger = JsonlAuditLedger(ledger_path)
        registry = ToolRegistry()
        policy = DefaultPolicyEngine()
        policy.load_rules([
            PolicyRule(rule_id="1", scope="filesystem.write", condition="", outcome=Outcome.ALLOW, priority=1)
        ])
        budget = DefaultBudgetEngine()
        risk = DefaultRiskEngine()
        hitl = SingleApprovalManager()
        
        # Register the REAL tool in the registry
        registry.register_tool(ToolDefinition(
            name="file.write",
            description="Writes a file to disk",
            input_schema={"filename": "string", "content": "string"},
            output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"],
            risk_level=RiskTier.LOW,
            reversible=True
        ))
        
        from tests.utils import build_test_gateway
        factory = AgentFactory(registry, policy, budget)
        
        # 1. Setup Parent State
        parent = AgentState(
            agent_id="system-root", role="system", type=AgentType.STATIC, goal="boot",
            permission_scope=["filesystem.write", "filesystem.read"], credential_scope=[], tool_scope=["file.write"],
            depth=0, ttl=datetime.timedelta(hours=1), expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            budget_ref="root-budget"
        )
        
        # 2. Spawn UniversalFileAgent
        spec = AgentSpec(
            request_id="req-1",
            requested_role="UniversalFileAgent",
            goal="Write a test file",
            parent_agent_id="system-root",
            requested_tools=["file.write"],
            requested_permission_scope=["filesystem.write"],
            ttl=datetime.timedelta(minutes=5),
            max_steps=5, max_tokens=100, max_children=2, dedup_hash="real-exec-abc"
        )
        
        child = factory.spawn_agent(spec, parent)
        
        # Build gateway but override with REAL LocalToolExecutor
        gateway = build_test_gateway(registry, policy, risk, budget, hitl, ledger, child)
        gateway.executor = LocalToolExecutor()
        
        # 3. Execute LangGraph Runtime
        graph = build_universal_file_graph()
        
        test_file_path = os.path.join(tmpdir, "hello_world.txt")
        test_content = "This is a real file created by the local tool executor."
        
        initial_state = {
            "agent_state": child,
            "payload": {"filename": test_file_path, "content": test_content},
            "plan": None,
            "tool_request": None,
            "receipt": None,
            "is_success": False,
            "gateway": gateway
        }
        
        # Set NAVA_TEST_MODE to bypass LLM call and avoid token burn during unit tests
        os.environ["NAVA_TEST_MODE"] = "1"
        
        final_state = graph.invoke(initial_state)
        
        # 4. Verify End-to-End Pipeline
        assert final_state["is_success"] is True
        assert final_state["receipt"] is not None
        
        # 5. Verify REAL Side Effects on Disk
        assert os.path.exists(test_file_path)
        with open(test_file_path, "r") as f:
            content = f.read()
            assert content == test_content
            
        # Clean up env
        del os.environ["NAVA_TEST_MODE"]
