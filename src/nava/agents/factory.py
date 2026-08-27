import uuid
import hashlib
from typing import Optional, List, Dict
from datetime import datetime
from nava.core.schemas import AgentSpec, AgentState, AgentType, AgentStatus, Outcome, ToolRequest
from nava.agents.templates import Templates, StaticAgentTemplate
from nava.tools.registry import ToolRegistry
from nava.gateway.pipeline import PolicyEngine, BudgetEngine

class AgentFactory:
    def __init__(self, registry: ToolRegistry, policy_engine: PolicyEngine, budget_engine: BudgetEngine):
        self.registry = registry
        self.policy_engine = policy_engine
        self.budget_engine = budget_engine

    def spawn_agent(self, spec: AgentSpec, parent_state: AgentState) -> AgentState:
        # 1. Budget & Depth Enforcement (Section 9.4)
        if not self.budget_engine.check_spawn(parent_state):
            raise RuntimeError(f"Budget exhausted for spawning new agents in task {parent_state.budget_ref}")
            
        if spec.max_children > 0 and len(parent_state.child_agent_ids) >= spec.max_children:
            raise ValueError(f"Exceeds max children limit of {spec.max_children}")
        
        # 2. Template Resolution (Section 9.2)
        template = Templates.get_template(spec.requested_role)
        
        is_dynamic = template is None
        agent_type = AgentType.DYNAMIC if is_dynamic else AgentType.STATIC
        template_id = template.template_id if template else None
        
        # 3. Dynamic Fallback & Scope Synthesis
        base_permission_scope = []
        base_tool_scope = []
        
        if not is_dynamic:
            base_permission_scope = template.permission_scope.copy()
            base_tool_scope = spec.requested_tools.copy() # Templates don't explicitly list tool scopes, they list permission scopes.
        else:
            # Dynamically synthesize scope by introspecting requested tools
            for tool_name in spec.requested_tools:
                try:
                    t_def = self.registry.get_tool(tool_name)
                    if t_def:
                        base_tool_scope.append(tool_name)
                        base_permission_scope.extend(t_def.permissions_required)
                except KeyError:
                    pass
            base_permission_scope = list(set(base_permission_scope))

        # 4. Permission Intersection (Section 9.3)
        # child_scope = parent_scope ∩ requested_scope ∩ policy_allowed_scope
        
        intersected_permissions = []
        intersected_tools = []
        
        # Helper to check scope match with wildcards (e.g. *, filesystem.*)
        def scope_matches(scope_pattern: str, target: str) -> bool:
            if scope_pattern == "*" or scope_pattern == target:
                return True
            if scope_pattern.endswith(".*"):
                prefix = scope_pattern[:-2]
                return target.startswith(prefix)
            return False

        def is_in_scope_list(scope_list: List[str], target: str) -> bool:
            return any(scope_matches(pattern, target) for pattern in scope_list)

        # Helper to query policy
        def is_allowed_by_policy(scope: str) -> bool:
            mock_req = ToolRequest(
                request_id="policy_check",
                agent_id="factory",
                tool_name=scope,
                arguments={},
                requested_scope=scope
            )
            eval_result = self.policy_engine.evaluate(mock_req, parent_state)
            return eval_result == Outcome.ALLOW
            
        # Intersect Permissions
        for req_perm in spec.requested_permission_scope:
            if is_in_scope_list(parent_state.permission_scope, req_perm) and is_in_scope_list(base_permission_scope, req_perm):
                if is_allowed_by_policy(req_perm):
                    if req_perm not in intersected_permissions:
                        intersected_permissions.append(req_perm)
                    
        # Intersect Tools and their inherent permissions
        for req_tool in spec.requested_tools:
            # 1. Hard Role-Based Tool Restrictions
            if req_tool.startswith(("context7.", "superpowers.")) and spec.requested_role != "CodingAgent":
                continue # Hard-reject AST developer MCPs for any agent other than CodingAgent
            if req_tool.startswith(("fetch.", "brave.", "arxiv.")) and spec.requested_role != "ResearchAgent":
                continue # Hard-reject Research MCPs for any agent other than ResearchAgent
            if req_tool.startswith(("sqlite.", "data.")) and spec.requested_role != "DataAgent":
                continue # Hard-reject Database & Tabular Analytics MCPs for any agent other than DataAgent
            if req_tool.startswith(("typst.", "doc.")) and spec.requested_role not in ["DocumentAgent", "UniversalFileAgent"]:
                continue # Hard-reject Typst compilation & Doc tools for agents other than DocumentAgent / UniversalFileAgent
            if req_tool.startswith(("audit.", "sequential_thinking.")) and spec.requested_role not in ["ReviewerAgent", "VerifierAgent"]:
                continue # Hard-reject Audit & Sequential Thinking tools for agents other than ReviewerAgent and VerifierAgent
            if req_tool.startswith("git.") and spec.requested_role not in ["CodingAgent", "TerminalAgent"]:
                continue
            if req_tool.startswith("desktop.") and spec.requested_role != "ComputerAgent":
                continue
            if req_tool.startswith(("terminal.", "docker.")) and spec.requested_role != "TerminalAgent":
                continue
                
            if (req_tool in parent_state.tool_scope or is_in_scope_list(parent_state.tool_scope, req_tool)) and req_tool in base_tool_scope:
                t_def = self.registry.get_tool(req_tool)
                if not t_def:
                    continue
                
                # Enforce invariant: A tool can only be granted if ALL its required permissions
                # fall within the agent's base template scope and parent scope.
                tool_permitted = True
                for p in t_def.permissions_required:
                    if not is_in_scope_list(base_permission_scope, p) or not is_in_scope_list(parent_state.permission_scope, p):
                        tool_permitted = False
                        break
                        
                if tool_permitted:
                    intersected_tools.append(req_tool)
                    
                    # Auto-inject the tool's required permissions if permitted
                    for p in t_def.permissions_required:
                        if is_in_scope_list(parent_state.permission_scope, p) and p not in intersected_permissions:
                            if is_allowed_by_policy(p):
                                intersected_permissions.append(p)

        # Intersect Credentials (Phase 6)
        # Credential scope must be a subset of permissions per Section 17.3
        intersected_credentials = []
        for req_tool in intersected_tools:
            t_def = self.registry.get_tool(req_tool)
            if t_def and t_def.required_credentials:
                for perm in t_def.permissions_required:
                    if is_in_scope_list(parent_state.credential_scope, perm) and perm not in intersected_credentials:
                        if perm in intersected_permissions: # Critical invariant check
                            intersected_credentials.append(perm)

        # 5. State Initialization
        # 5. Mint AgentState
        state = AgentState(
            agent_id=f"agt-{uuid.uuid4().hex[:8]}",
            parent_agent_id=parent_state.agent_id if parent_state else None,
            role=spec.requested_role,
            display_label=spec.display_label,
            type=agent_type,
            template_id=template_id,
            goal=spec.goal,
            permission_scope=intersected_permissions,
            credential_scope=intersected_credentials,
            tool_scope=intersected_tools,
            depth=(parent_state.depth + 1) if parent_state else 0,
            status=AgentStatus.PENDING,
            ttl=spec.ttl,
            expires_at=datetime.utcnow() + spec.ttl,
            budget_ref=parent_state.budget_ref
        )
        return state
