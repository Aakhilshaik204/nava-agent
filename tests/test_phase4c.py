import pytest
import datetime
import os
import tempfile
from nava.core.schemas import AgentSpec, AgentState, AgentType, Priority, ToolRequest, Outcome, RiskTier, AgentStatus, PolicyRule
from nava.agents.factory import AgentFactory
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.governance.risk_engine import DefaultRiskEngine
from nava.governance.hitl_manager import SingleApprovalManager
from nava.gateway.pipeline import ActionGateway
from nava.core.ledger import JsonlAuditLedger
from nava.agents.runtime.dynamic_graph import build_dynamic_graph

def test_phase4c_dynamic_agent():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger_path = os.path.join(tmpdir, "audit.jsonl")
        ledger = JsonlAuditLedger(ledger_path)
        registry = ToolRegistry()
        policy = DefaultPolicyEngine()
        policy.load_rules([
            PolicyRule(rule_id="1", scope="filesystem.write", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="2", scope="github.write", condition="", outcome=Outcome.ALLOW, priority=1)
        ])
        budget = DefaultBudgetEngine()
        risk = DefaultRiskEngine()
        hitl = SingleApprovalManager()
        
        # Register tools
        registry.register_tool(ToolDefinition(
            name="file.create_md", description="Creates MD",
            input_schema={"filename": "string"}, output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"], risk_level=RiskTier.LOW, reversible=True
        ))
        registry.register_tool(ToolDefinition(
            name="github.write", description="Push to github",
            input_schema={"repo": "string"}, output_schema={"success": "boolean"},
            permissions_required=["github.write"], risk_level=RiskTier.HIGH, reversible=False
        ))
        
        from tests.utils import build_test_gateway
        factory = AgentFactory(registry, policy, budget)
        
        # 1. Setup Parent State (Only has filesystem.write)
        parent = AgentState(
            agent_id="system-root", role="system", type=AgentType.STATIC, goal="boot",
            permission_scope=["filesystem.write"], credential_scope=[], tool_scope=["file.create_md"],
            depth=0, ttl=datetime.timedelta(hours=1), expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            budget_ref="root-budget"
        )
        
        # 2. Adversarial Scope Bounding (Section 32.2)
        # Requesting a tool (github.write) outside parent's bounds
        spec = AgentSpec(
            request_id="req-1", requested_role="UnknownAdHocAgent", goal="Do something",
            parent_agent_id="system-root",
            requested_tools=["file.create_md", "github.write"],
            requested_permission_scope=["filesystem.write", "github.write"],
            ttl=datetime.timedelta(minutes=5), max_steps=5, max_tokens=100, max_children=2, dedup_hash="exact-match-hash-1"
        )
        
        child = factory.spawn_agent(spec, parent)
        assert child.type == AgentType.DYNAMIC
        assert "filesystem.write" in child.permission_scope
        assert "github.write" not in child.permission_scope # BRUTALLY CLIPPED
        assert "github.write" not in child.tool_scope       # BRUTALLY CLIPPED
        
        gateway = build_test_gateway(registry, policy, risk, budget, hitl, ledger, child)
        
        # 3. Deduplication (Exact Match Only)
        spec2 = AgentSpec(
            request_id="req-2", requested_role="UnknownAdHocAgent", goal="Do something",
            parent_agent_id="system-root", requested_tools=["file.create_md", "github.write"],
            requested_permission_scope=["filesystem.write", "github.write"],
            ttl=datetime.timedelta(minutes=5), max_steps=5, max_tokens=100, max_children=2, dedup_hash="exact-match-hash-1"
        )
        assert spec.dedup_hash == spec2.dedup_hash
        
        # 4. End-to-End Dynamic Execution & Lifecycle
        graph = build_dynamic_graph()
        
        initial_state = {
            "agent_state": child,
            "payload": {"filename": "output.md"},
            "plan": None,
            "tool_requests": [],
            "receipts": [],
            "is_success": False,
            "gateway": gateway
        }
        
        os.environ["NAVA_TEST_MODE"] = "1"
        final_state = graph.invoke(initial_state)
        del os.environ["NAVA_TEST_MODE"]
        
        assert final_state["is_success"] is True
        assert len(final_state["receipts"]) == 1 # Only executed file.create_md because github.write was clipped!
        assert final_state["agent_state"].status == AgentStatus.TERMINATED # Invariant 16: Teardown
