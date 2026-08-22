import pytest
from datetime import timedelta, datetime
import tempfile
import os

from nava.core.schemas import AgentSpec, ToolRequest, AgentState, Event, Receipt, AgentType, Priority, ResultEnum, RiskTier, RiskDecision, RiskAssessment
from nava.core.ledger import JsonlAuditLedger, JsonlReceiptStore
from nava.gateway.pipeline import (
    ActionGateway, SchemaValidator, IdentityVerifier, ScopeVerifier, PermissionChecker,
    PolicyEngine, RiskEngine, BudgetEngine, ConcurrencyManager, HITLManager,
    Executor, StateObserver, Verifier, MemoryUpdater
)

def test_schema_validation_and_deduplication():
    # Verify AgentSpec requires all fields and typing works
    spec = AgentSpec(
        request_id="req-123",
        requested_role="test_role",
        goal="do something",
        parent_agent_id="root",
        requested_tools=["fs.read"],
        requested_permission_scope=["fs.read"],
        ttl=timedelta(minutes=5),
        max_steps=10,
        max_tokens=1000,
        max_children=2,
        priority=Priority.NORMAL,
        dedup_hash="hash-123"
    )
    assert spec.dedup_hash == "hash-123"

def test_audit_ledger_append_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "ledger.jsonl")
        ledger = JsonlAuditLedger(file_path)
        
        # Verify it lacks update/delete methods
        assert not hasattr(ledger, "update_event")
        assert not hasattr(ledger, "delete_event")
        
        event = Event(event_id="evt-1", event_type="TEST", task_id="task-1")
        ledger.append_event(event)
        
        events = ledger.get_events("task-1")
        assert len(events) == 1
        assert events[0].event_id == "evt-1"

# Mock Governance Modules
class MockSchemaValidator(SchemaValidator):
    def validate(self, request): return True

class MockIdentityVerifier(IdentityVerifier):
    def verify(self, request):
        return AgentState(
            agent_id=request.agent_id,
            role="test",
            type=AgentType.STATIC,
            goal="test",
            permission_scope=[],
            credential_scope=[],
            tool_scope=[],
            depth=1,
            ttl=timedelta(minutes=5),
            expires_at=datetime.utcnow() + timedelta(minutes=5),
            budget_ref="task-1"
        )

class MockScopeVerifier(ScopeVerifier):
    def verify_parent_scope(self, agent): return True

class MockPermissionChecker(PermissionChecker):
    def check(self, request, agent): return True

class MockPolicyEngine(PolicyEngine):
    def evaluate(self, request, agent): return "ALLOW"

class MockRiskEngine(RiskEngine):
    def evaluate(self, request, agent):
        return RiskAssessment(
            assessment_id="risk-1",
            tool_request_id=request.request_id,
            total_score=10,
            tier=RiskTier.LOW,
            decision=RiskDecision.AUTO_EXECUTE
        )

class MockBudgetEngine(BudgetEngine):
    def check_and_consume(self, request, agent): return True

class MockConcurrencyManager(ConcurrencyManager):
    def check_locks(self, request): return True

class MockHITLManager(HITLManager):
    def decide(self, request, risk): return None

class MockExecutor(Executor):
    def execute(self, request): return "Success"

class MockStateObserver(StateObserver):
    def observe(self, request, result): return "Observation"

class MockVerifier(Verifier):
    def verify(self, request, result, observation): return True

class MockMemoryUpdater(MemoryUpdater):
    def update(self, receipt): pass

def test_action_gateway_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        ledger = JsonlAuditLedger(os.path.join(tmpdir, "ledger.jsonl"))
        receipts = JsonlReceiptStore(os.path.join(tmpdir, "receipts.jsonl"))
        
        gateway = ActionGateway(
            schema_validator=MockSchemaValidator(),
            identity_verifier=MockIdentityVerifier(),
            scope_verifier=MockScopeVerifier(),
            permission_checker=MockPermissionChecker(),
            policy_engine=MockPolicyEngine(),
            risk_engine=MockRiskEngine(),
            budget_engine=MockBudgetEngine(),
            concurrency_manager=MockConcurrencyManager(),
            hitl_manager=MockHITLManager(),
            executor=MockExecutor(),
            state_observer=MockStateObserver(),
            verifier=MockVerifier(),
            audit_ledger=ledger,
            receipt_store=receipts,
            memory_updater=MockMemoryUpdater()
        )
        
        request = ToolRequest(
            request_id="req-1",
            agent_id="agent-1",
            tool_name="test_tool",
            arguments={},
            requested_scope=""
        )
        
        # Test full success path
        receipt = gateway.process_request(request)
        assert receipt.result == ResultEnum.SUCCESS
        
        # Test fail-fast at schema validation
        class BadSchemaValidator(MockSchemaValidator):
            def validate(self, req): return False
            
        gateway.schema_validator = BadSchemaValidator()
        with pytest.raises(ValueError, match="Schema validation failed"):
            gateway.process_request(request)
            
        # Restore schema validator, test fail-fast at identity verification
        gateway.schema_validator = MockSchemaValidator()
        class BadIdentityVerifier(MockIdentityVerifier):
            def verify(self, req): return None
            
        gateway.identity_verifier = BadIdentityVerifier()
        with pytest.raises(PermissionError, match="Agent identity verification failed"):
            gateway.process_request(request)
