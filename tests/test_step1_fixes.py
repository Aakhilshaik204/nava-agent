import sys
import os

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import unittest
import datetime
import uuid
import tempfile
from nava.core.schemas import (
    AgentState, AgentSpec, AgentType, AgentStatus, ToolRequest, PolicyRule, Outcome, 
    RiskAssessment, RiskTier, RiskDecision, Approval, ApprovalStatus, Event
)
from nava.gateway.pipeline import ActionGateway
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.risk_engine import DefaultRiskEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.governance.hitl_manager import SingleApprovalManager
from nava.core.ledger import JsonlAuditLedger, JsonlReceiptStore
from nava.agents.factory import AgentFactory
from nava.agents.runtime.reviewer_agent import build_reviewer_agent
from tests.utils import (
    DummySchemaValidator, DummyIdentityVerifier, DummyScopeVerifier, 
    DummyPermissionChecker, DummyConcurrencyManager, DummyExecutor,
    DummyStateObserver, DummyVerifier, DummyMemoryUpdater
)


class TestStep1Fixes(unittest.TestCase):
    def setUp(self):
        os.environ["NAVA_TEST_MODE"] = "1"
        self.tmpdir = tempfile.TemporaryDirectory()
        self.ledger_path = os.path.join(self.tmpdir.name, "audit.jsonl")
        self.receipts_path = os.path.join(self.tmpdir.name, "receipts.jsonl")
        
        self.registry = ToolRegistry()
        self.registry.register_tool(ToolDefinition(
            name="file.write", description="Writes file",
            input_schema={"filename": "string", "content": "string"},
            output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"],
            risk_level=RiskTier.LOW, reversible=True
        ))
        self.registry.register_tool(ToolDefinition(
            name="file.read", description="Reads file",
            input_schema={"filename": "string"},
            output_schema={"content": "string"},
            permissions_required=["filesystem.read"],
            risk_level=RiskTier.LOW, reversible=True
        ))

        self.policy = DefaultPolicyEngine()
        self.policy.load_rules([
            PolicyRule(rule_id="default-allow-1", scope="filesystem.*", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="default-allow-2", scope="file.*", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="default-allow-3", scope="test.*", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="default-allow-4", scope="code.*", condition="", outcome=Outcome.ALLOW, priority=1),
        ])
        self.risk = DefaultRiskEngine()
        self.budget = DefaultBudgetEngine()
        self.hitl = SingleApprovalManager()
        self.ledger = JsonlAuditLedger(self.ledger_path)
        self.receipt_store = JsonlReceiptStore(self.receipts_path)
        
        self.agent = AgentState(
            agent_id="agt-test-1",
            role="TestAgent",
            type=AgentType.DYNAMIC,
            goal="Test Goal",
            permission_scope=["filesystem.write", "filesystem.read"],
            credential_scope=[],
            tool_scope=["file.write", "file.read"],
            depth=1,
            status=AgentStatus.RUNNING,
            ttl=datetime.timedelta(minutes=10),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
            budget_ref="budget-1"
        )
        
        self.gateway = ActionGateway(
            schema_validator=DummySchemaValidator(),
            identity_verifier=DummyIdentityVerifier(self.agent),
            scope_verifier=DummyScopeVerifier(),
            permission_checker=DummyPermissionChecker(),
            policy_engine=self.policy,
            risk_engine=self.risk,
            budget_engine=self.budget,
            concurrency_manager=DummyConcurrencyManager(),
            hitl_manager=self.hitl,
            executor=DummyExecutor(),
            state_observer=DummyStateObserver(),
            verifier=DummyVerifier(),
            audit_ledger=self.ledger,
            receipt_store=self.receipt_store,
            memory_updater=DummyMemoryUpdater(),
            registry=self.registry
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_policy_block_enforced_in_gateway(self):
        """Invariant: Policy BLOCK outcome must be enforced and raise PermissionError."""
        self.policy.load_rules([
            PolicyRule(rule_id="r-block", scope="file.write", condition="", outcome=Outcome.BLOCK, priority=10)
        ])
        req = ToolRequest(
            request_id="req-1",
            agent_id=self.agent.agent_id,
            tool_name="file.write",
            arguments={"filename": "test.txt", "content": "hello"},
            requested_scope="filesystem.write"
        )
        with self.assertRaises(PermissionError) as ctx:
            self.gateway.process_request(req)
        self.assertIn("Action Gateway Policy BLOCKED", str(ctx.exception))

    def test_policy_approval_enforced_in_gateway(self):
        """Invariant: Policy APPROVAL outcome requires approved status."""
        self.policy.load_rules([
            PolicyRule(rule_id="r-app", scope="file.write", condition="", outcome=Outcome.APPROVAL, priority=10)
        ])
        req = ToolRequest(
            request_id="req-2",
            agent_id=self.agent.agent_id,
            tool_name="file.write",
            arguments={"filename": "test.txt", "content": "hello"},
            requested_scope="filesystem.write"
        )
        with self.assertRaises(PermissionError) as ctx:
            self.gateway.process_request(req)
        self.assertIn("HITL Approval required by policy", str(ctx.exception))

    def test_agent_ttl_expiration_enforced(self):
        """Invariant #16: Expired agent cannot execute actions past its TTL."""
        expired_agent = AgentState(
            agent_id="agt-expired",
            role="ExpiredAgent",
            type=AgentType.DYNAMIC,
            goal="Test",
            permission_scope=["filesystem.read"],
            credential_scope=[],
            tool_scope=["file.read"],
            depth=1,
            status=AgentStatus.RUNNING,
            ttl=datetime.timedelta(minutes=1),
            expires_at=datetime.datetime.utcnow() - datetime.timedelta(seconds=10), # EXPIRED
            budget_ref="budget-1"
        )
        self.gateway.identity_verifier = DummyIdentityVerifier(expired_agent)
        
        req = ToolRequest(
            request_id="req-exp",
            agent_id=expired_agent.agent_id,
            tool_name="file.read",
            arguments={"filename": "test.txt"},
            requested_scope="filesystem.read"
        )
        with self.assertRaises(TimeoutError) as ctx:
            self.gateway.process_request(req)
        self.assertIn("exceeded its TTL", str(ctx.exception))

    def test_single_approval_manager_request_approval(self):
        """Verify SingleApprovalManager implements request_approval cleanly."""
        req = ToolRequest(
            request_id="req-hitl-1",
            agent_id="agt-1",
            tool_name="file.delete",
            arguments={"filename": "critical.db"},
            requested_scope="filesystem.write"
        )
        approval = self.hitl.request_approval(req, context="CodingAgent stuck on infinite loop")
        self.assertIsNotNone(approval)
        self.assertEqual(approval.status, ApprovalStatus.PENDING)
        self.assertIn("file.delete", approval.group_key)
        self.assertIn(approval.approval_id, self.hitl.pending_approvals)

    def test_factory_depth_and_wildcard_permissions(self):
        """Verify AgentFactory handles wildcard permissions and proper depth limit."""
        factory = AgentFactory(self.registry, self.policy, self.budget)
        
        parent = AgentState(
            agent_id="agt-parent",
            role="Nava",
            type=AgentType.STATIC,
            goal="Parent Goal",
            permission_scope=["filesystem.*", "test.*"],
            credential_scope=[],
            tool_scope=["file.*"],
            depth=0,
            status=AgentStatus.RUNNING,
            ttl=datetime.timedelta(minutes=30),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=30),
            budget_ref="budget-1"
        )
        
        spec = AgentSpec(
            request_id="req-child",
            requested_role="DynamicAgent",
            goal="Child Goal",
            parent_agent_id=parent.agent_id,
            requested_tools=["file.write", "file.read"],
            requested_permission_scope=["filesystem.write", "filesystem.read"],
            ttl=datetime.timedelta(minutes=10),
            max_steps=10,
            max_tokens=1000,
            max_children=3,
            dedup_hash="dedup-1"
        )
        
        child = factory.spawn_agent(spec, parent)
        self.assertIsNotNone(child)
        self.assertEqual(child.depth, 1)
        self.assertIn("filesystem.write", child.permission_scope)
        self.assertIn("filesystem.read", child.permission_scope)
        self.assertIn("file.write", child.tool_scope)
        self.assertIn("file.read", child.tool_scope)

    def test_reviewer_agent_graph_execution(self):
        """Verify ReviewerAgent graph compiles and runs without double compile crash."""
        reviewer_graph = build_reviewer_agent(self.registry)
        self.assertIsNotNone(reviewer_graph)
        
        state = {
            "agent_state": self.agent,
            "payload": {},
            "plan": None,
            "tool_request": None,
            "observation": None,
            "gateway": self.gateway,
            "history": []
        }
        res = reviewer_graph.invoke(state)
        self.assertIsNotNone(res)
        self.assertEqual(res["plan"], "code.diff_review")

    def test_audit_ledger_append_event(self):
        """Verify AuditLedger append_event writes structured Event JSON."""
        evt = Event(
            event_id="evt-100",
            event_type="MCP_TOOL_APPROVED",
            task_id="task-1",
            payload={"server": "gmail", "tool": "gmail.read"}
        )
        self.ledger.append_event(evt)
        events = self.ledger.get_events("task-1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "MCP_TOOL_APPROVED")
        self.assertEqual(events[0].payload["tool"], "gmail.read")


if __name__ == "__main__":
    unittest.main()
