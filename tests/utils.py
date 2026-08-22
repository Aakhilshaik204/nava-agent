from typing import Optional, Any
from nava.gateway.pipeline import (
    ActionGateway, SchemaValidator, IdentityVerifier, ScopeVerifier, 
    PermissionChecker, ConcurrencyManager, Executor, StateObserver, 
    Verifier, MemoryUpdater, Receipt
)
from nava.core.ledger import ImmutableReceiptStore
from nava.core.schemas import ToolRequest, AgentState

# Minimal pass-throughs for interfaces not yet built in Phase 0-4
class DummySchemaValidator(SchemaValidator):
    def validate(self, request: ToolRequest) -> bool: return True

class DummyIdentityVerifier(IdentityVerifier):
    def __init__(self, agent: AgentState): self.agent = agent
    def verify(self, request: ToolRequest) -> AgentState: return self.agent

class DummyScopeVerifier(ScopeVerifier):
    def verify_parent_scope(self, agent: AgentState) -> bool: return True

class DummyPermissionChecker(PermissionChecker):
    def check(self, request: ToolRequest, agent: AgentState) -> bool: return True

class DummyConcurrencyManager(ConcurrencyManager):
    def check_locks(self, request: ToolRequest) -> bool: return True

class DummyExecutor(Executor):
    def execute(self, request: ToolRequest) -> Any: return {"status": "executed"}

class DummyStateObserver(StateObserver):
    def observe(self, request: ToolRequest, result: Any, pre_snapshot: Optional[Any] = None) -> Any: return None

class DummyVerifier(Verifier):
    def verify(self, request: ToolRequest, result: Any, observation: Any) -> bool: return True

class DummyReceiptStore(ImmutableReceiptStore):
    def store_receipt(self, receipt: Receipt) -> None: pass
    def get_receipt(self, receipt_id: str) -> Receipt: return None

class DummyMemoryUpdater(MemoryUpdater):
    def update(self, receipt: Receipt) -> None: pass

def build_test_gateway(registry, policy, risk, budget, hitl, ledger, agent: AgentState, receipt_store=None, concurrency_manager=None, credential_broker=None, state_observer=None, executor=None) -> ActionGateway:
    return ActionGateway(
        schema_validator=DummySchemaValidator(),
        identity_verifier=DummyIdentityVerifier(agent),
        scope_verifier=DummyScopeVerifier(),
        permission_checker=DummyPermissionChecker(),
        policy_engine=policy,
        risk_engine=risk,
        budget_engine=budget,
        concurrency_manager=concurrency_manager or DummyConcurrencyManager(),
        hitl_manager=hitl,
        executor=executor or DummyExecutor(),
        state_observer=state_observer or DummyStateObserver(),
        verifier=DummyVerifier(),
        audit_ledger=ledger,
        receipt_store=receipt_store or DummyReceiptStore(),
        memory_updater=DummyMemoryUpdater(),
        registry=registry,
        credential_broker=credential_broker
    )
