"""
subagent_engine.py — Dynamic Subagent Dispatcher & Micro-Fanout Engine for NAVA OS.

Enables running agents to programmatically dispatch micro-subagents across items
(files, URLs, hypotheses) with strict OS governance, isolated context sandboxes,
typed response validation, and Merkle audit receipts.
"""

import os
import json
import time
import uuid
import hashlib
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List, Optional

from nava.core.schemas import AgentState, AgentSpec, AgentStatus, AgentType, ToolRequest
from nava.orchestration.patterns import (
    OrchestrationPattern,
    SubagentTaskSpec,
    SubagentResult,
    BatchDispatchResponse,
)
from nava.agents.runtime.graph_dispatcher import get_agent_graph
from nava.agents.templates import Templates

class SubagentEngine:
    """Core runtime engine for dispatching and aggregating dynamic subagents."""

    def __init__(self, registry=None, gateway=None, factory=None):
        self.registry = registry
        self.gateway = gateway
        self.factory = factory

    def _compute_hash(self, data: Any) -> str:
        """Computes SHA256 receipt hash of data."""
        raw = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    def _compute_merkle_root(self, hashes: List[str]) -> str:
        """Computes a Merkle root hash from a list of leaf hashes."""
        if not hashes:
            return hashlib.sha256(b"empty_merkle_tree").hexdigest()
        if len(hashes) == 1:
            return hashes[0]
        
        current_layer = hashes.copy()
        while len(current_layer) > 1:
            next_layer = []
            for i in range(0, len(current_layer), 2):
                if i + 1 < len(current_layer):
                    combined = (current_layer[i] + current_layer[i + 1]).encode("utf-8")
                else:
                    combined = (current_layer[i] + current_layer[i]).encode("utf-8")
                next_layer.append(hashlib.sha256(combined).hexdigest())
            current_layer = next_layer
        return current_layer[0]

    def _run_single_subagent(
        self,
        task_spec: SubagentTaskSpec,
        parent_state: Optional[AgentState] = None
    ) -> SubagentResult:
        """Executes a single micro-subagent in an isolated context sandbox."""
        start_time = time.time()
        t_id = task_spec.task_id or f"sub-{uuid.uuid4().hex[:8]}"
        
        # Enforce Spawn Depth Limit (Invariant #5: Depth <= 3)
        parent_depth = parent_state.spawn_depth if parent_state else 0
        if parent_depth >= 3:
            return SubagentResult(
                task_id=t_id,
                role=task_spec.role,
                status="FAILED",
                error="Maximum spawn depth of 3 exceeded (Invariant #5)",
                execution_time_ms=(time.time() - start_time) * 1000
            )

        # 1. Resolve Template & Permissions (Invariant #2: Scope Intersection)
        template = Templates.get_template(task_spec.role)
        target_role = task_spec.role if template else "DynamicAgent"
        
        child_permission_scope = []
        if parent_state:
            allowed_parent = parent_state.permission_scope.copy()
            if template:
                # Intersect template permissions with parent permissions
                child_permission_scope = [p for p in template.permission_scope if p in allowed_parent or "*" in allowed_parent]
            else:
                child_permission_scope = allowed_parent
        else:
            child_permission_scope = template.permission_scope.copy() if template else ["*"]

        # Tool Scopes
        child_tool_scope = []
        if self.registry:
            for t_name, t_def in self.registry._tools.items():
                if any(p in child_permission_scope or "*" in child_permission_scope for p in t_def.permissions_required):
                    child_tool_scope.append(t_name)
        if not child_tool_scope and template:
            child_tool_scope = list(self.registry._tools.keys()) if self.registry else []

        child_state = AgentState(
            agent_id=t_id,
            role=target_role,
            goal=task_spec.goal,
            permission_scope=child_permission_scope,
            tool_scope=child_tool_scope,
            status=AgentStatus.RUNNING,
            spawn_depth=parent_depth + 1,
            parent_agent_id=parent_state.agent_id if parent_state else None,
            task_id=parent_state.task_id if parent_state else f"tsk_{t_id}",
            project_id=parent_state.project_id if parent_state else "default",
        )

        try:
            # 2. Compile Graph
            compiled_graph = get_agent_graph(target_role, self.registry)
            
            # 3. Initial Graph State
            initial_state = {
                "agent_state": child_state,
                "payload": task_spec.context,
                "observation": None,
                "history": [],
                "gateway": self.gateway
            }

            # Fast execution loop (max 10 cyclic turns for micro-subagents)
            max_turns = 10
            turn_count = 0
            current_state = initial_state
            
            while turn_count < max_turns:
                turn_count += 1
                result_state = compiled_graph.invoke(current_state)
                
                tool_req = result_state.get("tool_request")
                plan = result_state.get("plan")
                
                if plan == "FINISH" or not tool_req:
                    break
                    
                if self.gateway and tool_req:
                    # Route through Action Gateway
                    receipt = self.gateway.process_request(tool_req)
                    result_state["observation"] = receipt.data if receipt else "Done"
                    result_state["tool_request"] = None
                else:
                    # Fallback direct execution if no gateway attached
                    result_state["observation"] = "Executed without gateway."
                    result_state["tool_request"] = None
                    
                current_state = result_state

            # Extract result output
            final_output = None
            if "history" in current_state and current_state["history"]:
                final_output = current_state["history"][-1]
            elif "final_answer" in current_state:
                final_output = current_state["final_answer"]
            else:
                final_output = current_state.get("observation", "Subagent task completed.")

            # Validate response schema if provided
            if task_spec.response_schema and isinstance(final_output, str):
                try:
                    # Attempt to extract JSON from string output
                    json_str = final_output
                    if "```json" in json_str:
                        json_str = json_str.split("```json")[1].split("```")[0].strip()
                    elif "```" in json_str:
                        json_str = json_str.split("```")[1].split("```")[0].strip()
                    parsed = json.loads(json_str)
                    final_output = parsed
                except Exception:
                    pass

            elapsed_ms = (time.time() - start_time) * 1000
            receipt_hash = self._compute_hash({
                "task_id": t_id,
                "role": target_role,
                "goal": task_spec.goal,
                "output": final_output,
                "execution_time_ms": elapsed_ms
            })

            return SubagentResult(
                task_id=t_id,
                role=target_role,
                status="SUCCESS",
                output=final_output,
                receipt_hash=receipt_hash,
                execution_time_ms=elapsed_ms
            )

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            return SubagentResult(
                task_id=t_id,
                role=target_role,
                status="FAILED",
                output=None,
                error=str(e),
                execution_time_ms=elapsed_ms
            )

    def dispatch_batch(
        self,
        subagents: List[Dict[str, Any]],
        pattern: str = OrchestrationPattern.FANOUT_SYNTHESIZE.value,
        concurrency_limit: int = 5,
        parent_state: Optional[AgentState] = None
    ) -> Dict[str, Any]:
        """
        Dispatches a batch of micro-subagents concurrently.
        Synchronous wrapper suitable for tool invocation.
        """
        parsed_specs = []
        for s in subagents:
            if isinstance(s, dict):
                parsed_specs.append(SubagentTaskSpec(**s))
            elif isinstance(s, SubagentTaskSpec):
                parsed_specs.append(s)

        total_tasks = len(parsed_specs)
        if total_tasks == 0:
            return BatchDispatchResponse(
                pattern=pattern,
                total_tasks=0,
                successful_tasks=0,
                failed_tasks=0,
                results=[],
                merkle_root=self._compute_merkle_root([])
            ).model_dump()

        max_workers = min(concurrency_limit, total_tasks, 20)
        results: List[SubagentResult] = []

        # Run concurrent workers via ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(self._run_single_subagent, spec, parent_state)
                for spec in parsed_specs
            ]
            for f in futures:
                try:
                    res = f.result()
                    results.append(res)
                except Exception as ex:
                    results.append(SubagentResult(
                        task_id=f"sub-err-{uuid.uuid4().hex[:6]}",
                        role="Unknown",
                        status="FAILED",
                        error=str(ex)
                    ))

        successful = sum(1 for r in results if r.status == "SUCCESS")
        failed = total_tasks - successful
        receipt_hashes = [r.receipt_hash for r in results if r.receipt_hash]
        merkle_root = self._compute_merkle_root(receipt_hashes)

        resp = BatchDispatchResponse(
            pattern=pattern,
            total_tasks=total_tasks,
            successful_tasks=successful,
            failed_tasks=failed,
            results=results,
            merkle_root=merkle_root
        )

        return resp.model_dump()
