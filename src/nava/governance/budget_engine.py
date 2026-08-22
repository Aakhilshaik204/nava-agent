import threading
import hashlib
from typing import Dict
from nava.core.schemas import TaskBudget, BudgetStatus, AgentState, ToolRequest
from nava.gateway.pipeline import BudgetEngine

class DefaultBudgetEngine(BudgetEngine):
    def __init__(self):
        self.budgets: Dict[str, TaskBudget] = {}
        self._lock = threading.Lock()

    def register_budget(self, budget: TaskBudget):
        with self._lock:
            self.budgets[budget.task_id] = budget

    def _update_status(self, budget: TaskBudget) -> bool:
        pct_agents = budget.consumed_agents / budget.max_agents if budget.max_agents else 0
        pct_steps = budget.consumed_steps / budget.max_steps if budget.max_steps else 0
        pct_tokens = budget.consumed_tokens / budget.max_tokens if budget.max_tokens else 0
        
        max_pct = max(pct_agents, pct_steps, pct_tokens)

        if max_pct >= 1.0:
            budget.status = BudgetStatus.EXHAUSTED
            return False
        elif max_pct >= 0.9:
            budget.status = BudgetStatus.RESTRICTED_90
        elif max_pct >= 0.8:
            budget.status = BudgetStatus.WARNING_80
        else:
            budget.status = BudgetStatus.OK

        return True

    def check_and_consume(self, request: ToolRequest, agent: AgentState) -> bool:
        with self._lock:
            budget = self.budgets.get(agent.budget_ref)
            if not budget:
                return True # Allow if no budget is tracked for this agent (e.g., tests)
                
            budget.consumed_steps += 1
            return self._update_status(budget)

    def consume_internal_llm_call(self, budget_ref: str, tokens: int = 0) -> bool:
        """
        Allows components like the Planner or internal Verification steps to consume
        budget resources even if they don't invoke a formal ToolRequest through the Gateway.
        """
        with self._lock:
            budget = self.budgets.get(budget_ref)
            if not budget:
                return True
                
            budget.consumed_steps += 1
            budget.consumed_tokens += tokens
            return self._update_status(budget)

    def check_spawn(self, parent_agent: AgentState) -> bool:
        with self._lock:
            budget = self.budgets.get(parent_agent.budget_ref)
            if not budget:
                return True # Mock tests without budget
                
            if budget.status in [BudgetStatus.RESTRICTED_90, BudgetStatus.EXHAUSTED]:
                return False
                
            if budget.max_agents > 0 and budget.consumed_agents >= budget.max_agents:
                return False
                
            if budget.max_depth > 0 and parent_agent.depth >= budget.max_depth:
                return False
                
            budget.consumed_agents += 1
            return True

    def record_failure(self, agent: AgentState, failure_string: str) -> bool:
        """
        Implements Section 14.4 Runaway Loop Protection via Failure-State Hashing.
        Returns False if the loop must be terminated (max_retries reached for the exact same failure).
        """
        with self._lock:
            budget = self.budgets.get(agent.budget_ref)
            if not budget:
                return True
                
            if not hasattr(budget, 'failure_hashes'):
                budget.failure_hashes = {}
                
            # Hash the goal + failure reason
            hash_input = f"{agent.goal}:{failure_string}".encode('utf-8')
            state_hash = hashlib.sha256(hash_input).hexdigest()
            
            count = budget.failure_hashes.get(state_hash, 0) + 1
            budget.failure_hashes[state_hash] = count
            
            if count > budget.max_retries:
                budget.status = BudgetStatus.EXHAUSTED
                return False # Terminate loop
                
            return True

