import os
import json
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from nava.core.schemas import MemoryRecord, MemoryTier, MemoryTrustLevel, MemoryConflictState
from nava.memory.store import ProfileMemoryStore


class UserPersona(BaseModel):
    name: str = "User"
    role: str = "Developer / Architect"
    preferred_communication_style: str = "concise, direct, highly technical"
    working_hours: str = "09:00 - 18:00"
    timezone: str = "UTC"
    authorized_tool_preferences: List[str] = Field(default_factory=lambda: ["file.read", "file.write", "code.search"])
    security_constraints: List[str] = Field(default_factory=lambda: ["No unapproved wire transfers", "No credential exfiltration"])


class AITwinManager:
    """
    Manages the Tier 4 AI Twin persona and structured user facts (Section 6 & Section 22).
    Generates dynamic prompt instructions that align autonomous agents with user identity.
    """
    def __init__(self, profile_store: ProfileMemoryStore):
        self.profile_store = profile_store
        self._ensure_default_persona()

    def _ensure_default_persona(self):
        persona_record = self.profile_store._records.get("profile-ai-twin-persona")
        if not persona_record:
            default_persona = UserPersona()
            rec = MemoryRecord(
                memory_id="profile-ai-twin-persona",
                tier=MemoryTier.PROFILE,
                content=default_persona.model_dump(),
                source="user",
                confidence=1.0,
                importance=1.0,
                sensitivity="medium",
                trust_level=MemoryTrustLevel.VERIFIED,
                provenance=["initial_setup"]
            )
            self.profile_store.store(rec, explicit_user_action=True)

    def get_persona(self) -> UserPersona:
        rec = self.profile_store._records.get("profile-ai-twin-persona")
        if rec and isinstance(rec.content, dict):
            return UserPersona(**rec.content)
        return UserPersona()

    def update_persona(self, updates: Dict[str, Any], explicit_user_action: bool = True) -> UserPersona:
        persona = self.get_persona()
        data = persona.model_dump()
        data.update(updates)
        updated_persona = UserPersona(**data)
        
        rec = MemoryRecord(
            memory_id="profile-ai-twin-persona",
            tier=MemoryTier.PROFILE,
            content=updated_persona.model_dump(),
            source="user" if explicit_user_action else "inferred",
            confidence=1.0 if explicit_user_action else 0.7,
            importance=1.0,
            sensitivity="medium",
            trust_level=MemoryTrustLevel.VERIFIED if explicit_user_action else MemoryTrustLevel.UNVERIFIED,
            provenance=["user_update" if explicit_user_action else "agent_observation"]
        )
        self.profile_store.store(rec, explicit_user_action=explicit_user_action)
        return updated_persona

    def get_system_persona_prompt(self) -> str:
        """
        Generates structured persona prompt for system prompt injection.
        """
        persona = self.get_persona()
        lines = [
            "\n[AI TWIN USER PERSONA & CONSTRAINTS (Section 6)]",
            f"- User Name / Role: {persona.name} ({persona.role})",
            f"- Communication Style: {persona.preferred_communication_style}",
            f"- Timezone / Working Hours: {persona.timezone} ({persona.working_hours})",
            f"- Primary Tool Preferences: {', '.join(persona.authorized_tool_preferences)}",
            "- Strict Constraints:"
        ]
        for c in persona.security_constraints:
            lines.append(f"  * {c}")
            
        # Append any additional verified profile facts
        verified_facts = [
            f"- {k}: {r.content}" for k, r in self.profile_store._records.items()
            if r.trust_level == MemoryTrustLevel.VERIFIED and k != "profile-ai-twin-persona"
        ]
        if verified_facts:
            lines.append("- Additional Verified Facts:")
            lines.extend(verified_facts)
            
        return "\n".join(lines)

    def get_conflicts(self) -> List[MemoryRecord]:
        """Returns all profile memories currently in CONFLICT_DETECTED state."""
        return [
            r for r in self.profile_store._records.values()
            if r.conflict_state == MemoryConflictState.CONFLICT_DETECTED
        ]
