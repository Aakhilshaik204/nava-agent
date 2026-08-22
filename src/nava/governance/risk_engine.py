import datetime
from typing import Dict, Any, List, Optional
from nava.core.schemas import RiskTier, ToolRequest, AgentState, RiskAssessment
from nava.gateway.pipeline import RiskEngine

from nava.memory.store import ProfileMemoryStore

class DefaultRiskEngine(RiskEngine):
    def __init__(self, profile_store: ProfileMemoryStore = None):
        # Baseline scoring matrix (Section 14.1)
        self.matrix = {
            "external_recipient": 30,
            "attachment": 20,
            "unknown_contact": 25,
            "sensitive_file": 40,
            "outside_working_hours": 15
        }
        self.profile_store = profile_store

    def is_external_recipient(self, recipient: str) -> bool:
        # In a real system, domains would be listed in Profile Memory.
        # For this implementation, we query if the domain is flagged as internal.
        domain = recipient.split("@")[-1] if "@" in recipient else ""
        if self.profile_store:
            matches = self.profile_store.retrieve(f"internal_domain:{domain}")
            if matches:
                return False
        return not recipient.endswith("@internal.com") # Default fallback

    def is_unknown_contact(self, recipient: str) -> bool:
        if self.profile_store:
            matches = self.profile_store.retrieve(f"contact:{recipient}")
            if matches:
                return False
        return not recipient.startswith("alice") and not recipient.startswith("bob")

    def is_sensitive_file(self, filename: str) -> bool:
        if not filename:
            return False
        lower = str(filename).lower()
        sensitive_keywords = ["secret", "resume", "financial", "password", ".env", "id_rsa", "credential", "private_key", ".vault_key", "vault.json"]
        return any(kw in lower for kw in sensitive_keywords)

    def is_outside_working_hours(self, dt: Optional[datetime.datetime]) -> bool:
        if not dt:
            dt = datetime.datetime.utcnow()
        if self.profile_store:
            matches = self.profile_store.retrieve("working_hours")
            # e.g., could parse "9-17" from content
        return dt.hour < 9 or dt.hour >= 17

    def evaluate(self, request: ToolRequest, agent: AgentState) -> RiskAssessment:
        score = 0
        factors = []
        
        # 1. External Recipient & Unknown Contact
        recipient = request.arguments.get("recipient", "")
        if recipient:
            if self.is_external_recipient(recipient):
                score += self.matrix["external_recipient"]
                factors.append({"name": "External recipient", "weight": self.matrix["external_recipient"]})
            if self.is_unknown_contact(recipient):
                score += self.matrix["unknown_contact"]
                factors.append({"name": "Unknown contact", "weight": self.matrix["unknown_contact"]})

        # 2. Attachments & Direct Sensitive Files
        attachments = request.arguments.get("attachments", [])
        if attachments:
            score += self.matrix["attachment"]
            factors.append({"name": "Attachment", "weight": self.matrix["attachment"]})
            for att in attachments:
                if self.is_sensitive_file(att):
                    score += self.matrix["sensitive_file"]
                    factors.append({"name": f"Sensitive file ({att})", "weight": self.matrix["sensitive_file"]})
                    break

        direct_file = request.arguments.get("filename") or request.arguments.get("target_file") or request.arguments.get("file_path")
        if direct_file and self.is_sensitive_file(direct_file):
            score += self.matrix["sensitive_file"]
            factors.append({"name": f"Sensitive target file ({direct_file})", "weight": self.matrix["sensitive_file"]})

        # 3. Dangerous Shell/Terminal Commands
        command = request.arguments.get("command") or request.arguments.get("cmd") or request.arguments.get("script")
        if command:
            cmd_lower = str(command).lower()
            dangerous_cmd_patterns = ["rm -rf", "drop database", "format", "del /f", "chmod 777", "curl | bash", "wget | bash"]
            if any(p in cmd_lower for p in dangerous_cmd_patterns):
                score += 50
                factors.append({"name": f"High-risk command ({command[:30]})", "weight": 50})

        # 3b. High-Risk Desktop GUI Actions (Blueprint Sec 21 & Pillar A)
        if request.tool_name.startswith("desktop."):
            args_str = str(request.arguments).lower()
            risky_gui_keywords = ["delete", "confirm order", "transfer", "pay", "buy now", "format", "erase", "shutdown", "alt+f4"]
            if any(k in args_str for k in risky_gui_keywords):
                score += 55
                factors.append({"name": f"High-risk Desktop GUI action ({request.tool_name})", "weight": 55})

        # 4. Outside Working Hours
        if self.is_outside_working_hours(request.created_at):
            score += self.matrix["outside_working_hours"]
            factors.append({"name": "Outside working hours", "weight": self.matrix["outside_working_hours"]})
            
        from nava.core.schemas import RiskDecision

        # Determine Tier
        if score <= 19:
            tier = RiskTier.LOW
            decision = RiskDecision.AUTO_EXECUTE
        elif score <= 49:
            tier = RiskTier.MEDIUM
            decision = RiskDecision.NOTIFY
        elif score <= 74:
            tier = RiskTier.HIGH
            decision = RiskDecision.HITL
        else:
            tier = RiskTier.CRITICAL
            decision = RiskDecision.BLOCK
            
        return RiskAssessment(
            assessment_id="risk_" + request.request_id,
            tool_request_id=request.request_id,
            factors=factors,
            total_score=score,
            tier=tier,
            decision=decision,
            computed_at=datetime.datetime.now()
        )
