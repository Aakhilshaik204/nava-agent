from enum import Enum
from typing import List, Optional, Any, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

# ---------------------------------------------------------
# Enumerations
# ---------------------------------------------------------

class AgentType(str, Enum):
    STATIC = "STATIC"
    DYNAMIC = "DYNAMIC"

class AgentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TERMINATED = "TERMINATED"

class Priority(str, Enum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"

class Outcome(str, Enum):
    ALLOW = "ALLOW"
    APPROVAL = "APPROVAL"
    BLOCK = "BLOCK"

class PolicySource(str, Enum):
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"
    USER_DEFINED = "USER_DEFINED"

class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class RiskDecision(str, Enum):
    AUTO_EXECUTE = "AUTO_EXECUTE"
    NOTIFY = "NOTIFY"
    HITL = "HITL"
    BLOCK = "BLOCK"

class BudgetStatus(str, Enum):
    OK = "OK"
    WARNING_80 = "WARNING_80"
    RESTRICTED_90 = "RESTRICTED_90"
    EXHAUSTED = "EXHAUSTED"

class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"

class ResultEnum(str, Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    PARTIAL = "PARTIAL"
    
    # Mechanical undo crashed (e.g. file locked). Intervention needed.
    ROLLBACK_FAILED = "ROLLBACK_FAILED"
    
    # Mechanical undo impossible (tool reversible=False). Route to CompensationEngine.
    COMPENSATION_UNAVAILABLE = "COMPENSATION_UNAVAILABLE"

class StatePhase(str, Enum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"

class MemoryTier(str, Enum):
    WORKING = "WORKING"
    EPISODIC = "EPISODIC"
    SEMANTIC = "SEMANTIC"
    PROFILE = "PROFILE"

class MemoryTrustLevel(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTED = "CONFLICTED"

class MemoryApprovalState(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DISMISSED = "DISMISSED"

class MemoryConflictState(str, Enum):
    NONE = "NONE"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    RESOLVED = "RESOLVED"

# ---------------------------------------------------------
# Core Models
# ---------------------------------------------------------

class TaskBudget(BaseModel):
    task_id: str
    max_agents: int
    max_depth: int
    max_steps: int
    max_tokens: int
    max_runtime: timedelta
    max_retries: int
    
    consumed_agents: int = 0
    consumed_steps: int = 0
    consumed_tokens: int = 0
    consumed_runtime: timedelta = timedelta(seconds=0)
    failure_hashes: Dict[str, int] = Field(default_factory=dict)
    
    status: BudgetStatus = BudgetStatus.OK

class AgentState(BaseModel):
    agent_id: str
    parent_agent_id: Optional[str] = None
    role: str
    display_label: Optional[str] = None
    type: AgentType
    template_id: Optional[str] = None
    goal: str
    permission_scope: List[str]
    credential_scope: List[str]
    tool_scope: List[str]
    depth: int
    status: AgentStatus = AgentStatus.PENDING
    ttl: timedelta
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    budget_ref: str # uuid -> TaskBudget
    step_count: int = 0
    token_count: int = 0
    child_agent_ids: List[str] = Field(default_factory=list)

class AgentSpec(BaseModel):
    request_id: str
    requested_role: str
    display_label: Optional[str] = None
    goal: str
    parent_agent_id: str
    requested_tools: List[str]
    requested_permission_scope: List[str]
    ttl: timedelta
    max_steps: int
    max_tokens: int
    max_children: int
    priority: Priority = Priority.NORMAL
    dedup_hash: str
    stage: int = 1
    is_parallel: bool = True


class ToolRequest(BaseModel):
    request_id: str
    agent_id: str
    tool_name: str
    arguments: Dict[str, Any]
    requested_scope: str
    credential_ids: List[str] = Field(default_factory=list)
    dry_run: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PolicyRule(BaseModel):
    rule_id: str
    scope: str
    condition: str
    outcome: Outcome
    priority: int
    source: PolicySource = PolicySource.SYSTEM_DEFAULT
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RiskFactor(BaseModel):
    name: str
    weight: int

class RiskAssessment(BaseModel):
    assessment_id: str
    tool_request_id: str
    factors: List[RiskFactor] = Field(default_factory=list)
    total_score: int
    tier: RiskTier
    decision: RiskDecision
    computed_at: datetime = Field(default_factory=datetime.utcnow)

class Approval(BaseModel):
    approval_id: str
    tool_request_ids: List[str] = Field(default_factory=list)
    group_key: str
    combined_risk_tier: RiskTier
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[str] = None

class Receipt(BaseModel):
    receipt_id: str
    task_id: str
    agent_id: str
    parent_agent_id: str
    tool_name: str
    action_summary: str
    policy_evaluation: List[PolicyRule] = Field(default_factory=list)
    risk_assessment: RiskAssessment
    approval: Optional[Approval] = None
    result: ResultEnum
    result_data: Any = None
    executed_at: datetime = Field(default_factory=datetime.utcnow)

class StateSnapshot(BaseModel):
    snapshot_id: str
    resource_ref: str
    phase: StatePhase
    content_hash: str
    content_ref: str
    captured_at: datetime = Field(default_factory=datetime.utcnow)

class Event(BaseModel):
    event_id: str
    event_type: str
    task_id: str
    agent_id: Optional[str] = None
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MemoryRecord(BaseModel):
    memory_id: str
    tier: MemoryTier
    content: Any
    source: str
    confidence: float
    importance: float
    expiration: Optional[datetime] = None
    sensitivity: str
    user_editable: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Section 31.1 Security metadata
    provenance: List[str] = Field(default_factory=list)
    trust_level: MemoryTrustLevel = MemoryTrustLevel.UNVERIFIED
    approval_state: Optional[MemoryApprovalState] = None
    conflict_state: MemoryConflictState = MemoryConflictState.NONE
