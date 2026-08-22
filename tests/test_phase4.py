import pytest
import datetime
import os
import tempfile
from nava.core.schemas import AgentSpec, AgentState, AgentType, Priority, ToolRequest, Outcome, RiskTier, AgentStatus, BudgetStatus, PolicyRule
from nava.agents.factory import AgentFactory
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.governance.risk_engine import DefaultRiskEngine
from nava.governance.hitl_manager import SingleApprovalManager
from nava.gateway.pipeline import ActionGateway
from nava.core.ledger import JsonlAuditLedger
from nava.agents.runtime.universal_file_graph import build_universal_file_graph

def test_phase4_integration_universal_file():
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
        
        # Register a mock tool in the registry
        registry.register_tool(ToolDefinition(
            name="file.create_txt",
            description="Creates a TXT file",
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
            permission_scope=["filesystem.write", "filesystem.read"], credential_scope=[], tool_scope=["file.create_txt"],
            depth=0, ttl=datetime.timedelta(hours=1), expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            budget_ref="root-budget"
        )
        
        # 2. Spawn UniversalFileAgent
        spec = AgentSpec(
            request_id="req-1",
            requested_role="UniversalFileAgent",
            goal="Write a file",
            parent_agent_id="system-root",
            requested_tools=["file.create_txt"],
            requested_permission_scope=["filesystem.write"],
            ttl=datetime.timedelta(minutes=5),
            max_steps=5, max_tokens=100, max_children=2, dedup_hash="abc"
        )
        
        child = factory.spawn_agent(spec, parent)
        assert child.type == AgentType.STATIC
        assert child.depth == 1
        assert "filesystem.write" in child.permission_scope
        
        gateway = build_test_gateway(registry, policy, risk, budget, hitl, ledger, child)
        
        # 3. Execute LangGraph Runtime
        graph = build_universal_file_graph()
        
        initial_state = {
            "agent_state": child,
            "payload": {"filename": "output.txt", "content": "Hello World"},
            "plan": None,
            "tool_request": None,
            "receipt": None,
            "is_success": False,
            "gateway": gateway
        }
        
        os.environ["NAVA_TEST_MODE"] = "1"
        final_state = graph.invoke(initial_state)
        del os.environ["NAVA_TEST_MODE"]
        
        # 4. Verify End-to-End Pipeline
        assert final_state["is_success"] is True
        assert final_state["receipt"] is not None
        assert final_state["receipt"].result.value == "SUCCESS"
        assert final_state["agent_state"].status == AgentStatus.TERMINATED # Invariant 16 Teardown
        
        # 5. Verify Ledger Emits
        events = ledger.get_events(child.goal)
        # Should have ActionGateway writes + explicitly emitted VERIFICATION_PASSED
        verification_events = [e for e in events if getattr(e, 'event_type', '') == "VERIFICATION_PASSED"]
        assert len(verification_events) == 1
