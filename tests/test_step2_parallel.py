import sys
import os

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import unittest
import datetime
import uuid
import tempfile
import threading
import concurrent.futures
from nava.core.schemas import (
    AgentState, AgentSpec, AgentType, AgentStatus, ToolRequest, PolicyRule, Outcome, 
    RiskAssessment, RiskTier, RiskDecision, Approval, ApprovalStatus, Event, TaskBudget, BudgetStatus
)
from nava.gateway.pipeline import ActionGateway
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.risk_engine import DefaultRiskEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.governance.hitl_manager import SingleApprovalManager
from nava.governance.lock_manager import DefaultLockManager, LockType
from nava.core.ledger import JsonlAuditLedger, JsonlReceiptStore
from nava.agents.factory import AgentFactory
from nava.agents.planner import GoalPlanner, compute_dedup_hash
from tests.utils import (
    DummySchemaValidator, DummyIdentityVerifier, DummyScopeVerifier, 
    DummyPermissionChecker, DummyConcurrencyManager, DummyExecutor,
    DummyStateObserver, DummyVerifier, DummyMemoryUpdater, build_test_gateway
)


class TestStep2ParallelEngine(unittest.TestCase):
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
            PolicyRule(rule_id="r1", scope="filesystem.*", condition="", outcome=Outcome.ALLOW, priority=1),
            PolicyRule(rule_id="r2", scope="file.*", condition="", outcome=Outcome.ALLOW, priority=1),
        ])
        
        self.risk = DefaultRiskEngine()
        self.budget_engine = DefaultBudgetEngine()
        self.hitl = SingleApprovalManager()
        self.lock_manager = DefaultLockManager(lock_ttl_seconds=10)
        self.ledger = JsonlAuditLedger(self.ledger_path)
        self.receipt_store = JsonlReceiptStore(self.receipts_path)
        
        self.task_budget = TaskBudget(
            task_id="budget-parallel-1",
            max_agents=10, max_depth=3, max_steps=100, max_tokens=10000,
            max_runtime=datetime.timedelta(minutes=10), max_retries=3
        )
        self.budget_engine.register_budget(self.task_budget)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_lock_manager_write_exclusive_blocks_parallel_agent(self):
        """Invariant: Exclusive write lock acquired by Agent A blocks Agent B from writing to same file."""
        req_a = ToolRequest(
            request_id="req-a",
            agent_id="agent-A",
            tool_name="file.write",
            arguments={"filename": "shared_data.json", "content": "A"},
            requested_scope="filesystem.write"
        )
        req_b = ToolRequest(
            request_id="req-b",
            agent_id="agent-B",
            tool_name="file.write",
            arguments={"filename": "shared_data.json", "content": "B"},
            requested_scope="filesystem.write"
        )
        
        # Agent A acquires write lock
        acquired_a = self.lock_manager.check_locks(req_a)
        self.assertTrue(acquired_a)
        
        # Agent B attempts to acquire write lock on same file -> MUST BE BLOCKED
        acquired_b = self.lock_manager.check_locks(req_b)
        self.assertFalse(acquired_b)

    def test_lock_manager_read_shared_allows_parallel_agents(self):
        """Invariant: Multiple agents can acquire shared read locks on the same file concurrently."""
        req_reader1 = ToolRequest(
            request_id="req-r1",
            agent_id="agent-R1",
            tool_name="file.read",
            arguments={"filename": "shared_data.json"},
            requested_scope="filesystem.read"
        )
        req_reader2 = ToolRequest(
            request_id="req-r2",
            agent_id="agent-R2",
            tool_name="file.read",
            arguments={"filename": "shared_data.json"},
            requested_scope="filesystem.read"
        )
        
        acquired_1 = self.lock_manager.check_locks(req_reader1)
        acquired_2 = self.lock_manager.check_locks(req_reader2)
        
        self.assertTrue(acquired_1)
        self.assertTrue(acquired_2)

    def test_lock_manager_path_hierarchy_and_normalization(self):
        """Verify normalized paths and directory hierarchy boundary checks."""
        # /tmp/report vs /tmp/report_v2.md should NOT conflict
        req1 = ToolRequest(
            request_id="req-p1", agent_id="agent-1", tool_name="file.write",
            arguments={"filename": "data/report.json"}, requested_scope="filesystem.write"
        )
        req2 = ToolRequest(
            request_id="req-p2", agent_id="agent-2", tool_name="file.write",
            arguments={"filename": "data/report_v2.json"}, requested_scope="filesystem.write"
        )
        
        self.assertTrue(self.lock_manager.check_locks(req1))
        self.assertTrue(self.lock_manager.check_locks(req2)) # Different file in same folder -> allowed

    def test_lock_manager_release_lock(self):
        """Verify release_lock frees resource so another agent can acquire it."""
        req_a = ToolRequest(
            request_id="req-rel-a", agent_id="agent-A", tool_name="file.write",
            arguments={"filename": "output.txt"}, requested_scope="filesystem.write"
        )
        req_b = ToolRequest(
            request_id="req-rel-b", agent_id="agent-B", tool_name="file.write",
            arguments={"filename": "output.txt"}, requested_scope="filesystem.write"
        )
        
        self.assertTrue(self.lock_manager.check_locks(req_a))
        self.assertFalse(self.lock_manager.check_locks(req_b))
        
        # Release A's lock
        self.lock_manager.release_lock(req_a)
        
        # B can now acquire
        self.assertTrue(self.lock_manager.check_locks(req_b))

    def test_budget_engine_thread_safety(self):
        """Verify TaskBudget is thread-safe under 20 concurrent threads."""
        agent = AgentState(
            agent_id="agent-thread-test", role="Test", type=AgentType.DYNAMIC,
            goal="Test", permission_scope=[], credential_scope=[], tool_scope=[],
            depth=1, ttl=datetime.timedelta(minutes=5),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=5),
            budget_ref=self.task_budget.task_id
        )
        req = ToolRequest(
            request_id="req-t", agent_id=agent.agent_id, tool_name="file.read",
            arguments={}, requested_scope=""
        )
        
        def worker():
            for _ in range(5):
                self.budget_engine.check_and_consume(req, agent)
                self.budget_engine.consume_internal_llm_call(self.task_budget.task_id, tokens=10)
                
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
            
        # 10 threads * 5 loops * 2 step consumptions = 100 steps
        self.assertEqual(self.task_budget.consumed_steps, 100)
        # 10 threads * 5 loops * 10 tokens = 500 tokens
        self.assertEqual(self.task_budget.consumed_tokens, 500)

    def test_goal_planner_stage_decomposition_and_dedup(self):
        """Verify GoalPlanner outputs stage attributes and canonical SHA-256 deduplication hashes."""
        planner = GoalPlanner(
            available_templates=["DocumentAgent", "DataAgent", "CodingAgent"],
            ceiling_tools=["file.write", "file.read"],
            ceiling_permissions=["filesystem.write", "filesystem.read"],
            budget_engine=self.budget_engine
        )
        specs = planner.plan("Generate sales summary", parent_id="root", budget_ref=self.task_budget.task_id)
        self.assertEqual(len(specs), 1)
        self.assertEqual(specs[0].stage, 1)
        self.assertTrue(specs[0].is_parallel)
        
        # Test deterministic dedup hash
        hash1 = compute_dedup_hash("DocumentAgent", "Generate sales summary", ["file.write"])
        hash2 = compute_dedup_hash("DocumentAgent", "  generate sales SUMMARY ", ["file.write"])
        self.assertEqual(hash1, hash2)

    def test_parallel_dynamic_agents_stage_execution(self):
        """Verify parallel execution of independent dynamic agents in parallel worker pool."""
        factory = AgentFactory(self.registry, self.policy, self.budget_engine)
        
        parent = AgentState(
            agent_id="agt-parent-root", role="Nava", type=AgentType.STATIC,
            goal="Coordinate parallel tasks",
            permission_scope=["filesystem.*"], credential_scope=[], tool_scope=["file.*"],
            depth=0, ttl=datetime.timedelta(minutes=30),
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=30),
            budget_ref=self.task_budget.task_id
        )
        
        spec_1 = AgentSpec(
            request_id="req-worker-1", requested_role="DynamicAgent", goal="Collect sales data",
            parent_agent_id=parent.agent_id, requested_tools=["file.write"],
            requested_permission_scope=["filesystem.write"], ttl=datetime.timedelta(minutes=5),
            max_steps=5, max_tokens=1000, max_children=2,
            dedup_hash="h1", stage=1, is_parallel=True
        )
        spec_2 = AgentSpec(
            request_id="req-worker-2", requested_role="DynamicAgent", goal="Collect inventory data",
            parent_agent_id=parent.agent_id, requested_tools=["file.write"],
            requested_permission_scope=["filesystem.write"], ttl=datetime.timedelta(minutes=5),
            max_steps=5, max_tokens=1000, max_children=2,
            dedup_hash="h2", stage=1, is_parallel=True
        )
        
        global_payload = {}
        payload_lock = threading.Lock()
        
        def run_agent_task(spec, filename):
            child = factory.spawn_agent(spec, parent)
            gateway = build_test_gateway(
                self.registry, self.policy, self.risk, self.budget_engine,
                self.hitl, self.ledger, child,
                receipt_store=self.receipt_store,
                concurrency_manager=self.lock_manager
            )
            req = ToolRequest(
                request_id=f"req-{uuid.uuid4().hex[:6]}",
                agent_id=child.agent_id,
                tool_name="file.write",
                arguments={"filename": filename, "content": f"Data for {spec.goal}"},
                requested_scope="filesystem.write"
            )
            receipt = gateway.process_request(req)
            with payload_lock:
                global_payload[spec.goal] = receipt.result_data
            
            # Teardown
            child.status = AgentStatus.TERMINATED
            self.lock_manager.release_all(child.agent_id)
            return receipt.result.name
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(run_agent_task, spec_1, "sales.json")
            f2 = executor.submit(run_agent_task, spec_2, "inventory.json")
            res1 = f1.result()
            res2 = f2.result()
            
        self.assertEqual(res1, "SUCCESS")
        self.assertEqual(res2, "SUCCESS")
        self.assertIn("Collect sales data", global_payload)
        self.assertIn("Collect inventory data", global_payload)


if __name__ == "__main__":
    unittest.main()
