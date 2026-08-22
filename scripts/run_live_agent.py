import os
import datetime
from nava.core.schemas import AgentSpec, AgentState, AgentType, Outcome, RiskTier, AgentStatus, PolicyRule
from nava.agents.factory import AgentFactory
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.governance.risk_engine import DefaultRiskEngine
from nava.governance.hitl_manager import SingleApprovalManager
from nava.core.ledger import JsonlAuditLedger
from nava.agents.runtime.tier1_graphs import build_document_agent
from nava.tools.executor import LocalToolExecutor
from tests.utils import build_test_gateway

def run_live():
    print("--- Starting LIVE Nava Agent ---")
    # MUST have GOOGLE_API_KEY set
    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY environment variable is not set!")
        return

    ledger = JsonlAuditLedger("live_audit.jsonl")
    registry = ToolRegistry()
    policy = DefaultPolicyEngine()
    policy.load_rules([
        PolicyRule(rule_id="1", scope="filesystem.write", condition="", outcome=Outcome.ALLOW, priority=1),
        PolicyRule(rule_id="2", scope="filesystem.read", condition="", outcome=Outcome.ALLOW, priority=1)
    ])
    budget = DefaultBudgetEngine()
    risk = DefaultRiskEngine()
    hitl = SingleApprovalManager()
    
    registry.register_tool(ToolDefinition(
        name="file.write",
        description="Writes a file to disk",
        input_schema={"filename": "string", "content": "string"},
        output_schema={"success": "boolean"},
        permissions_required=["filesystem.write"],
        risk_level=RiskTier.LOW,
        reversible=True
    ))

    registry.register_tool(ToolDefinition(
        name="file.read",
        description="Reads a file from disk",
        input_schema={"filename": "string"},
        output_schema={"content": "string"},
        permissions_required=["filesystem.read"],
        risk_level=RiskTier.LOW,
        reversible=True
    ))

    factory = AgentFactory(registry, policy, budget)
    
    parent = AgentState(
        agent_id="system-root", role="system", type=AgentType.STATIC, goal="boot",
        permission_scope=["filesystem.write", "filesystem.read"], credential_scope=[], tool_scope=["file.write", "file.read"],
        depth=0, ttl=datetime.timedelta(hours=1), expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
        budget_ref="root-budget"
    )
    
    spec = AgentSpec(
        request_id="req-live-1",
        requested_role="DocumentAgent",
        goal="Write a file named hello.txt containing a friendly greeting to the user.",
        parent_agent_id="system-root",
        requested_tools=["file.write", "file.read"],
        requested_permission_scope=["filesystem.write", "filesystem.read"],
        ttl=datetime.timedelta(minutes=5),
        max_steps=5, max_tokens=1000, max_children=2, dedup_hash="live-1"
    )
    
    child = factory.spawn_agent(spec, parent)
    
    gateway = build_test_gateway(registry, policy, risk, budget, hitl, ledger, child)
    gateway.executor = LocalToolExecutor()
    
    graph = build_document_agent()
    
    print(f"Goal: {child.goal}")
    print("Invoking LLM...")
    
    initial_state = {
        "agent_state": child,
        "payload": {},
        "plan": None,
        "tool_request": None,
        "receipt": None,
        "is_success": False,
        "gateway": gateway
    }
    
    # Ensure test mode is OFF
    if "NAVA_TEST_MODE" in os.environ:
        del os.environ["NAVA_TEST_MODE"]

    final_state = graph.invoke(initial_state)
    
    print(f"Agent finished. Success: {final_state['is_success']}")
    if final_state["receipt"]:
        print(f"Receipt action: {final_state['receipt'].action_summary}")
        print(f"Receipt result: {final_state['receipt'].result}")

if __name__ == "__main__":
    run_live()
