from abc import ABC, abstractmethod
import uuid
from datetime import datetime
from typing import Optional, Any
from nava.core.schemas import (
    ToolRequest, AgentState, Receipt, Event, RiskAssessment, Approval, ApprovalStatus, ResultEnum, RiskTier, RiskDecision, Outcome
)
from nava.core.ledger import AuditLedger, ImmutableReceiptStore

class SchemaValidator(ABC):
    @abstractmethod
    def validate(self, request: ToolRequest) -> bool: pass

class IdentityVerifier(ABC):
    @abstractmethod
    def verify(self, request: ToolRequest) -> AgentState: pass

class ScopeVerifier(ABC):
    @abstractmethod
    def verify_parent_scope(self, agent: AgentState) -> bool: pass

class PermissionChecker(ABC):
    @abstractmethod
    def check(self, request: ToolRequest, agent: AgentState) -> bool: pass

class PolicyEngine(ABC):
    @abstractmethod
    def evaluate(self, request: ToolRequest, agent: AgentState) -> Any: pass

class RiskEngine(ABC):
    @abstractmethod
    def evaluate(self, request: ToolRequest, agent: AgentState) -> RiskAssessment: pass

class BudgetEngine(ABC):
    @abstractmethod
    def check_and_consume(self, request: ToolRequest, agent: AgentState) -> bool: pass
    
    @abstractmethod
    def check_spawn(self, parent_agent: AgentState) -> bool: pass

class ConcurrencyManager(ABC):
    @abstractmethod
    def check_locks(self, request: ToolRequest) -> bool: pass

class HITLManager(ABC):
    @abstractmethod
    def decide(self, request: ToolRequest, risk: RiskAssessment) -> Optional[Approval]: pass

class Executor(ABC):
    @abstractmethod
    def execute(self, request: ToolRequest) -> Any: pass

class StateObserver(ABC):
    @abstractmethod
    def observe(self, request: ToolRequest, result: Any, pre_snapshot: Optional[Any] = None) -> Any: pass

class Verifier(ABC):
    @abstractmethod
    def verify(self, request: ToolRequest, result: Any, observation: Any) -> bool: pass

class MemoryUpdater(ABC):
    @abstractmethod
    def update(self, receipt: Receipt) -> None: pass


class ActionGateway:
    """
    Central trust boundary for NAVA.
    All mutating tool requests MUST pass through this exact sequence.
    """
    def __init__(
        self,
        schema_validator: SchemaValidator,
        identity_verifier: IdentityVerifier,
        scope_verifier: ScopeVerifier,
        permission_checker: PermissionChecker,
        policy_engine: PolicyEngine,
        risk_engine: RiskEngine,
        budget_engine: BudgetEngine,
        concurrency_manager: ConcurrencyManager,
        hitl_manager: HITLManager,
        executor: Executor,
        state_observer: StateObserver,
        verifier: Verifier,
        audit_ledger: AuditLedger,
        receipt_store: ImmutableReceiptStore,
        memory_updater: MemoryUpdater,
        registry = None,
        credential_broker = None
    ):
        self.schema_validator = schema_validator
        self.identity_verifier = identity_verifier
        self.scope_verifier = scope_verifier
        self.permission_checker = permission_checker
        self.policy_engine = policy_engine
        self.risk_engine = risk_engine
        self.budget_engine = budget_engine
        self.concurrency_manager = concurrency_manager
        self.hitl_manager = hitl_manager
        self.executor = executor
        self.state_observer = state_observer
        self.verifier = verifier
        self.audit_ledger = audit_ledger
        self.receipt_store = receipt_store
        self.memory_updater = memory_updater
        self.registry = registry
        self.credential_broker = credential_broker
        self.is_emergency_stopped = False
        self._emergency_event = None

    def process_request(self, request: ToolRequest) -> Receipt:
        # Step 0a: Emergency Kill Switch Check (Section 31.4 & Invariant #18)
        if self.is_emergency_stopped or (self._emergency_event and self._emergency_event.is_set()):
            self._log_event(getattr(request, "task_id", "emergency"), "EMERGENCY_HALT_BLOCKED", {"tool": request.tool_name})
            raise RuntimeError("Emergency kill switch is active. All operations halted.")

        # Step 0b: Emit TOOL_REQUESTED event
        self._log_event(request.task_id if hasattr(request, 'task_id') else "unknown_task", 
                        "TOOL_REQUESTED", {"tool": request.tool_name, "request_id": request.request_id})

        # Step 1: Schema Validation
        if not self.schema_validator.validate(request):
            raise ValueError(f"Schema validation failed for request {request.request_id}")

        # Step 2: Agent Identity
        agent = self.identity_verifier.verify(request)
        if not agent:
            raise PermissionError(f"Agent identity verification failed for {request.agent_id}")

        # Step 2b: Agent TTL Check (Section 9.5 / Invariant #16)
        if hasattr(agent, 'expires_at') and agent.expires_at:
            if datetime.utcnow() > agent.expires_at:
                raise TimeoutError(f"Agent {agent.agent_id} has exceeded its TTL and expired at {agent.expires_at}")

        # Step 3: Parent Scope Verification
        if not self.scope_verifier.verify_parent_scope(agent):
            raise PermissionError(f"Parent scope verification failed for agent {agent.agent_id}")

        # Step 4: Permission Check
        if not self.permission_checker.check(request, agent):
            raise PermissionError(f"Permission check failed for {request.tool_name}")

        # Step 5: Policy Evaluation
        policy_result = self.policy_engine.evaluate(request, agent)
        self._log_event(agent.budget_ref, "POLICY_EVALUATED", {"result": str(policy_result)})
        if policy_result == Outcome.BLOCK:
            raise PermissionError(f"Action Gateway Policy BLOCKED execution of {request.tool_name}")

        # Step 6: Risk Evaluation
        risk_assessment = self.risk_engine.evaluate(request, agent)
        tool_def = self.registry.tools.get(request.tool_name) if self.registry else None
        
        # If tool does not exist in registry, return failure receipt to allow model self-correction
        if self.registry and request.tool_name not in self.registry.tools and not request.tool_name.startswith("system."):
            available_tools = list(self.registry.tools.keys())
            err_msg = f"Tool '{request.tool_name}' not found in registry. Please use one of the available tools: {available_tools}"
            return Receipt(
                receipt_id=str(uuid.uuid4()),
                task_id=agent.budget_ref,
                agent_id=agent.agent_id,
                parent_agent_id=agent.parent_agent_id or "ROOT",
                tool_name=request.tool_name,
                action_summary=f"Attempted invalid tool {request.tool_name}",
                policy_evaluation=[],
                risk_assessment=risk_assessment,
                approval=None,
                result=ResultEnum.FAILURE,
                result_data={"error": err_msg, "success": False}
            )
        
        # Override calculated risk if the tool's base risk is higher
        if tool_def and getattr(tool_def, "risk_level", None):
            tier_weights = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            base_weight = tier_weights.get(tool_def.risk_level.value, 1)
            calc_weight = tier_weights.get(risk_assessment.tier.value, 1)
            
            if base_weight > calc_weight:
                risk_assessment.tier = tool_def.risk_level
                
        self._log_event(agent.budget_ref, "RISK_CALCULATED", {"tier": risk_assessment.tier})

        # Step 7: Budget Check (Stubbed for Phase 0)
        if not self.budget_engine.check_and_consume(request, agent):
            raise RuntimeError(f"Budget exhausted for agent {agent.agent_id}")

        # Step 8: Concurrency Check
        if not self.concurrency_manager.check_locks(request):
            raise RuntimeError(f"Concurrency lock acquisition failed for {request.tool_name}")

        try:
            # Step 9: Credential Scope (Section 17.3)
            if tool_def and tool_def.required_credentials:
                for service in tool_def.required_credentials:
                    try:
                        # Request scoped credential for this service
                        cred = self.credential_broker.request_credential(
                            agent=agent, 
                            service=service, 
                            requested_scope=tool_def.permissions_required
                        )
                        request.credential_ids.append(cred.credential_id)
                        self._log_event(agent.budget_ref, "CREDENTIAL_ISSUED", {"service": service})
                    except PermissionError as e:
                        raise PermissionError(f"Credential Broker denied access to {service}: {e}")
                    except Exception as e:
                        raise RuntimeError(f"Credential Vault error for {service}: {e}")
            
            # Step 10: HITL Decision
            if policy_result == Outcome.APPROVAL:
                # Policy explicitly requires human approval regardless of base risk
                approval = self.hitl_manager.decide(request, risk_assessment)
                if not isinstance(approval, Approval) or getattr(approval, "status", None) not in ["APPROVED", ApprovalStatus.APPROVED]:
                    if isinstance(approval, Approval):
                        self._log_event(agent.budget_ref, "APPROVAL_REQUIRED", {"approval_id": approval.approval_id})
                    raise PermissionError(f"HITL Approval required by policy for {request.tool_name}")
                self._log_event(agent.budget_ref, "APPROVAL_GRANTED", {"approval_id": getattr(approval, "approval_id", "unknown")})
            else:
                approval = self.hitl_manager.decide(request, risk_assessment)
                if isinstance(approval, Outcome):
                    if approval != Outcome.ALLOW:
                        raise PermissionError(f"HITL approval denied or blocked for {request.tool_name}")
                elif approval:
                    status_val = getattr(approval, "status", None)
                    if status_val not in ["APPROVED", ApprovalStatus.APPROVED]:
                        self._log_event(agent.budget_ref, "APPROVAL_REQUIRED", {"approval_id": getattr(approval, "approval_id", "unknown")})
                        raise PermissionError(f"HITL Approval required or rejected for {request.tool_name}")
                    self._log_event(agent.budget_ref, "APPROVAL_GRANTED", {"approval_id": getattr(approval, "approval_id", "unknown")})

            # Step 11: Dry Run Check
            if request.dry_run:
                return self._generate_dry_run_receipt(request, agent, risk_assessment)

            # Step 11b: Pre-State Observation (Phase 7)
            pre_snapshot = None
            if hasattr(self.state_observer, 'capture_before'):
                pre_snapshot = self.state_observer.capture_before(request)

            # Step 12: Execute
            result = self.executor.execute(request)
            self._log_event(agent.budget_ref, "TOOL_EXECUTED", {"tool": request.tool_name})

            # Step 13: State Observation
            observation = self.state_observer.observe(request, result, pre_snapshot) if pre_snapshot else self.state_observer.observe(request, result)

            # Step 14: Verification
            verification_passed = self.verifier.verify(request, result, observation)
            
            # Check if the executor specifically returned a failure dict or error string
            if isinstance(result, dict):
                if observation:
                    result["_observation"] = observation
                if "error" in result or result.get("success") is False:
                    verification_passed = False
                
            if verification_passed:
                self._log_event(agent.budget_ref, "VERIFICATION_PASSED", {})
            else:
                self._log_event(agent.budget_ref, "VERIFICATION_FAILED", {"result": result})
            
            final_result = ResultEnum.SUCCESS if verification_passed else ResultEnum.FAILURE
            
            print("\n================= LIVE RESULTS =================")
            print(f"Tool: {request.tool_name}")
            print(f"Status: {final_result.name}")
            print(f"Data: {result}")
            print("================================================\n")

            # Step 15: Receipt Generation
            receipt = Receipt(
                receipt_id=str(uuid.uuid4()),
                task_id=agent.budget_ref,
                agent_id=agent.agent_id,
                parent_agent_id=agent.parent_agent_id or "ROOT",
                tool_name=request.tool_name,
                action_summary=f"Executed {request.tool_name}",
                policy_evaluation=[],
                risk_assessment=risk_assessment,
                approval=approval if not isinstance(approval, Outcome) else None,
                result=final_result,
                result_data=result
            )

            # Step 16: Audit Ledger (Receipt) Append
            self.receipt_store.store_receipt(receipt)
            self._log_event(agent.budget_ref, "STATE_CHANGED", {"receipt_id": receipt.receipt_id})

            # Step 17: Memory Update
            self.memory_updater.update(receipt)

            return receipt
        finally:
            if hasattr(self.concurrency_manager, "release_lock"):
                self.concurrency_manager.release_lock(request)

    def _log_event(self, task_id: str, event_type: str, payload: dict):
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            task_id=task_id,
            payload=payload
        )
        self.audit_ledger.append_event(event)

    def _generate_dry_run_receipt(self, request, agent, risk) -> Receipt:
        return Receipt(
            receipt_id=str(uuid.uuid4()),
            agent_id=agent.agent_id,
            parent_agent_id=agent.parent_agent_id or "ROOT",
            tool_name=request.tool_name,
            action_summary="DRY RUN",
            policy_evaluation=[],
            risk_assessment=risk,
            result=ResultEnum.SUCCESS
        )
