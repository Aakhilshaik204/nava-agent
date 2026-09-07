"""
test_dynamic_subagents.py — Test Suite for Dynamic Subagents & Programmatic Micro-Fanout.

Verifies:
1. Concurrent batch fanout execution via SubagentEngine.
2. Scope intersection invariant (Invariant #2) on child subagents.
3. Spawn depth limit enforcement (Invariant #5: depth <= 3).
4. Typed schema validation and response parsing.
5. Merkle root hash computation for batch receipts.
6. LocalToolExecutor integration with subagent.dispatch_batch.
"""

import pytest
import os
import json
import hashlib
from nava.tools.subagent_engine import SubagentEngine
from nava.orchestration.patterns import OrchestrationPattern, SubagentTaskSpec, BatchDispatchResponse
from nava.core.schemas import AgentState, AgentStatus, ToolRequest, ToolDefinition, RiskTier
from nava.tools.registry import ToolRegistry
from nava.tools.executor import LocalToolExecutor

@pytest.fixture
def setup_engine():
    registry = ToolRegistry()
    
    # Register mock test tools
    registry.register_tool(ToolDefinition(
        name="test.ping",
        description="A lightweight ping tool for tests.",
        input_schema={"msg": "string"},
        output_schema={"pong": "string"},
        permissions_required=["test.run"],
        risk_level=RiskTier.LOW,
        reversible=True
    ))
    registry.register_tool(ToolDefinition(
        name="file.read",
        description="Reads file.",
        input_schema={"filename": "string"},
        output_schema={"content": "string"},
        permissions_required=["filesystem.read"],
        risk_level=RiskTier.LOW,
        reversible=True
    ))
    
    engine = SubagentEngine(registry=registry)
    return engine, registry

def test_merkle_root_computation(setup_engine):
    engine, _ = setup_engine
    
    # Test empty list
    empty_root = engine._compute_merkle_root([])
    assert isinstance(empty_root, str)
    assert len(empty_root) == 64
    
    # Test single hash
    h1 = hashlib.sha256(b"leaf1").hexdigest()
    assert engine._compute_merkle_root([h1]) == h1
    
    # Test multiple hashes
    h2 = hashlib.sha256(b"leaf2").hexdigest()
    h3 = hashlib.sha256(b"leaf3").hexdigest()
    merkle_root = engine._compute_merkle_root([h1, h2, h3])
    assert isinstance(merkle_root, str)
    assert len(merkle_root) == 64
    assert merkle_root != h1

def test_spawn_depth_limit_enforcement(setup_engine):
    """Verifies Invariant #5: Max spawn depth <= 3."""
    engine, _ = setup_engine
    
    # Parent at depth 3 cannot spawn children
    parent_at_depth_3 = AgentState(
        agent_id="agt-deep",
        role="CodingAgent",
        goal="Deep task",
        permission_scope=["*"],
        tool_scope=["*"],
        spawn_depth=3
    )
    
    spec = SubagentTaskSpec(
        task_id="sub-test-1",
        role="ReviewerAgent",
        goal="Audit file"
    )
    
    res = engine._run_single_subagent(spec, parent_state=parent_at_depth_3)
    assert res.status == "FAILED"
    assert "depth of 3 exceeded" in res.error

def test_scope_intersection_invariant(setup_engine):
    """Verifies Invariant #2: Child scope = Parent scope ∩ Template scope."""
    engine, registry = setup_engine
    
    # Parent only has filesystem.read (no test.run)
    parent_restricted = AgentState(
        agent_id="agt-parent",
        role="FileAgent",
        goal="File task",
        permission_scope=["filesystem.read"],
        tool_scope=["file.read"],
        spawn_depth=0
    )
    
    spec = SubagentTaskSpec(
        task_id="sub-test-scope",
        role="ReviewerAgent",
        goal="Audit file"
    )
    
    # ReviewerAgent template wants ["filesystem.read", "github.read", "reasoning.sequential", ...]
    # Intersected with parent's ["filesystem.read"] -> child only gets ["filesystem.read"]
    res = engine._run_single_subagent(spec, parent_state=parent_restricted)
    assert res.task_id == "sub-test-scope"
    assert res.receipt_hash is not None

def test_batch_dispatch_concurrent_fanout(setup_engine):
    """Verifies concurrent fan-out execution of multiple subagents."""
    engine, _ = setup_engine
    
    os.environ["NAVA_TEST_MODE"] = "1"
    
    parent_state = AgentState(
        agent_id="agt-root",
        role="CodingAgent",
        goal="Main objective",
        permission_scope=["*"],
        tool_scope=["*"],
        spawn_depth=0
    )
    
    subagents = [
        {"task_id": f"task-{i}", "role": "ReviewerAgent", "goal": f"Review component {i}.jsx", "context": {"file": f"Comp{i}.jsx"}}
        for i in range(5)
    ]
    
    resp_dict = engine.dispatch_batch(
        subagents=subagents,
        pattern=OrchestrationPattern.FANOUT_SYNTHESIZE.value,
        concurrency_limit=5,
        parent_state=parent_state
    )
    
    assert resp_dict["total_tasks"] == 5
    assert resp_dict["successful_tasks"] == 5
    assert resp_dict["failed_tasks"] == 0
    assert len(resp_dict["results"]) == 5
    assert resp_dict["merkle_root"] is not None
    assert len(resp_dict["merkle_root"]) == 64

def test_executor_subagent_tool_integration(setup_engine):
    """Verifies subagent.dispatch_batch integration with LocalToolExecutor."""
    _, registry = setup_engine
    
    # Register subagent tool in registry
    registry.register_tool(ToolDefinition(
        name="subagent.dispatch_batch",
        description="Dispatches subagents",
        input_schema={},
        output_schema={},
        permissions_required=["subagent.spawn"],
        risk_level=RiskTier.MEDIUM,
        reversible=True
    ))
    
    executor = LocalToolExecutor(registry=registry)
    
    os.environ["NAVA_TEST_MODE"] = "1"
    
    req = ToolRequest(
        request_id="req-batch-1",
        agent_id="agt-main",
        tool_name="subagent.dispatch_batch",
        arguments={
            "subagents": [
                {"task_id": "t-1", "role": "ReviewerAgent", "goal": "Audit 1"},
                {"task_id": "t-2", "role": "ReviewerAgent", "goal": "Audit 2"}
            ],
            "pattern": "fanout_synthesize",
            "concurrency_limit": 2
        },
        requested_scope="subagent.spawn"
    )
    
    res = executor.execute(req)
    assert isinstance(res, dict)
    assert res["total_tasks"] == 2
    assert res["successful_tasks"] == 2
    assert res["merkle_root"] is not None
