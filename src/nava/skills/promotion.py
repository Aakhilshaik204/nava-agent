import os
import re
import json
import hashlib
from typing import Dict, List, Optional, Any
from datetime import datetime
from pydantic import BaseModel

from nava.core.schemas import AgentState, Receipt
from nava.skills.manager import SkillManager, SkillDefinition, SkillTrustState


class PromotionCandidate(BaseModel):
    task_id: str
    agent_id: str
    goal: str
    tools_used: List[str]
    permissions_used: List[str]
    steps_summary: List[Dict[str, Any]]
    suggested_name: str
    suggested_description: str
    created_at: str = ""


class SkillPromoter:
    """
    Manages user-governed dynamic skill promotion (Section 9.7 & Section 10).
    Captures multi-step workflows as candidates, requiring explicit user approval
    before generating and hash-locking new SKILL.md bundles.
    """
    def __init__(self, skill_manager: SkillManager, base_skills_dir: Optional[str] = None):
        self.skill_manager = skill_manager
        self.base_skills_dir = base_skills_dir or os.path.join(os.getcwd(), ".nava", "skills")
        self.candidates: Dict[str, PromotionCandidate] = {} # keyed by agent_id or task_id

    def evaluate_and_propose_candidate(
        self, 
        agent_state: AgentState, 
        receipts: List[Receipt],
        goal: str
    ) -> Optional[PromotionCandidate]:
        """
        Evaluates completed execution. If the workflow executed successful mutating or multi-step
        operations, creates a promotion candidate for user consideration.
        Does NOT promote automatically.
        """
        if not receipts:
            return None

        # Extract tools and steps
        actual_tools = list(dict.fromkeys([getattr(r, 'tool_name', 'tool') for r in receipts]))
        if not actual_tools and agent_state.tool_scope:
            actual_tools = agent_state.tool_scope

        # Clean suggested name
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', goal.lower().strip())[:30].strip('_')
        if not clean_name:
            clean_name = f"skill_{agent_state.agent_id[:8]}"

        steps = []
        for i, r in enumerate(receipts):
            steps.append({
                "step": i + 1,
                "action": getattr(r, 'tool_name', 'action'),
                "status": r.result.name if hasattr(r.result, 'name') else str(r.result)
            })

        candidate = PromotionCandidate(
            task_id=agent_state.budget_ref or f"task-{agent_state.agent_id[:8]}",
            agent_id=agent_state.agent_id,
            goal=goal,
            tools_used=actual_tools,
            permissions_used=agent_state.permission_scope,
            steps_summary=steps,
            suggested_name=clean_name,
            suggested_description=f"Automated workflow for: {goal}",
            created_at=datetime.utcnow().isoformat()
        )

        self.candidates[agent_state.agent_id] = candidate
        return candidate

    def list_candidates(self) -> List[PromotionCandidate]:
        return list(self.candidates.values())

    def get_candidate(self, identifier: str) -> Optional[PromotionCandidate]:
        if identifier in self.candidates:
            return self.candidates[identifier]
        for c in self.candidates.values():
            if c.task_id == identifier or c.suggested_name == identifier:
                return c
        return None

    def reject_candidate(self, identifier: str) -> bool:
        candidate = self.get_candidate(identifier)
        if candidate and candidate.agent_id in self.candidates:
            del self.candidates[candidate.agent_id]
            return True
        return False

    def promote_candidate(
        self,
        identifier: str,
        custom_name: Optional[str] = None,
        custom_description: Optional[str] = None,
        actor: str = "local_user"
    ) -> SkillDefinition:
        """
        Explicitly promotes an approved candidate into a hash-locked SKILL.md bundle on disk.
        Requires explicit user action (e.g. /skill promote <name>).
        """
        candidate = self.get_candidate(identifier)
        if not candidate:
            raise ValueError(f"No promotion candidate found for identifier: '{identifier}'.")

        skill_name = (custom_name or candidate.suggested_name).strip().lower().replace(" ", "_")
        description = custom_description or candidate.suggested_description

        # Prepare YAML frontmatter and instructions body (sorted deterministically)
        tools_formatted = ", ".join(f"'{t}'" for t in sorted(candidate.tools_used))
        perms_formatted = ", ".join(f"'{p}'" for p in sorted(candidate.permissions_used))

        skill_md_content = f"""---
name: {skill_name}
description: {description}
tools: [{tools_formatted}]
permissions: [{perms_formatted}]
promoted_from_agent: {candidate.agent_id}
promoted_at: {datetime.utcnow().isoformat()}
---

# {skill_name.replace('_', ' ').title()}

## Objective
{candidate.goal}

## Required Capabilities
- Tools: {', '.join(candidate.tools_used)}
- Permissions: {', '.join(candidate.permissions_used)}

## Execution Workflow
"""
        for s in candidate.steps_summary:
            skill_md_content += f"{s['step']}. Execute `{s['action']}` ({s['status']})\n"

        skill_dir = os.path.join(self.base_skills_dir, skill_name)
        os.makedirs(skill_dir, exist_ok=True)
        skill_file = os.path.join(skill_dir, "SKILL.md")

        with open(skill_file, "w", encoding="utf-8") as f:
            f.write(skill_md_content)

        # Refresh SkillManager so it discovers the new file
        self.skill_manager.refresh_skills()

        # Automatically hash and approve in the ledger if requested by user action
        self.skill_manager.approve_skill(skill_name, approved_by=actor)

        # Remove from pending candidates
        if candidate.agent_id in self.candidates:
            del self.candidates[candidate.agent_id]

        promoted_skill = self.skill_manager.get_skill(skill_name)
        if not promoted_skill:
            raise RuntimeError(f"Skill '{skill_name}' was written but failed to load in SkillManager.")

        print(f"[SkillPromoter] Successfully promoted and trusted skill: '{skill_name}' at {skill_file}")
        return promoted_skill
