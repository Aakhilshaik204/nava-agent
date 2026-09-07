"""
patterns.py — Core Orchestration Patterns for Dynamic Subagents in NAVA OS.

Defines the 6 foundational patterns:
1. Fanout and Synthesize (Batch mapping and aggregation)
2. Adversarial Verification (Two-pass confirmation and refutation)
3. Generate and Filter (Multi-candidate generation with scoring)
4. Tournament (Pairwise elimination bracket)
5. Loop Until Done (Fixed-point convergence discovery)
6. Classify and Act (Triage and specialized routing)
"""

from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class OrchestrationPattern(str, Enum):
    FANOUT_SYNTHESIZE = "fanout_synthesize"
    ADVERSARIAL_VERIFY = "adversarial_verify"
    GENERATE_FILTER = "generate_filter"
    TOURNAMENT = "tournament"
    LOOP_UNTIL_DONE = "loop_until_done"
    CLASSIFY_ACT = "classify_act"

class SubagentTaskSpec(BaseModel):
    task_id: Optional[str] = None
    role: str = Field(default="ReviewerAgent", description="The specialized agent role to execute this task.")
    goal: str = Field(description="The concrete instruction and target for this micro-subagent.")
    context: Dict[str, Any] = Field(default_factory=dict, description="Input payload or data context for the subagent.")
    response_schema: Optional[Dict[str, Any]] = Field(default=None, description="Expected JSON schema for the subagent output.")
    timeout_seconds: int = Field(default=60, description="Max execution time in seconds.")

class SubagentResult(BaseModel):
    task_id: str
    role: str
    status: str = "SUCCESS"  # SUCCESS, FAILED, TIMEOUT
    output: Any = None
    receipt_hash: Optional[str] = None
    execution_time_ms: float = 0.0
    error: Optional[str] = None

class BatchDispatchResponse(BaseModel):
    pattern: str
    total_tasks: int
    successful_tasks: int
    failed_tasks: int
    results: List[SubagentResult]
    merkle_root: Optional[str] = None
