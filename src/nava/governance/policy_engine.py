from typing import List, Optional, Dict
import fnmatch
from nava.core.schemas import ToolRequest, AgentState, PolicyRule, Outcome
from nava.gateway.pipeline import PolicyEngine

class DefaultPolicyEngine(PolicyEngine):
    """
    Deterministic Policy Engine with User-Configurable Security Switches (Blueprint Section 13).
    Allows immediate toggling of high-risk capabilities (terminal, GUI automation, external integrations).
    """
    def __init__(self, security_switches: Optional[Dict[str, bool]] = None):
        self.rules: List[PolicyRule] = []
        self.security_switches: Dict[str, bool] = security_switches or {
            "enable_terminal_execution": True,
            "enable_desktop_gui_control": True,
            "enable_external_integrations": True
        }

    def update_security_switch(self, switch_name: str, enabled: bool) -> None:
        """Dynamically updates a security feature switch."""
        self.security_switches[switch_name] = enabled

    def load_rules(self, rules: List[PolicyRule]) -> None:
        self.rules = rules

    def evaluate(self, request: ToolRequest, agent: AgentState) -> Outcome:
        # 1. Master Security Feature Switch Gating
        if not self.security_switches.get("enable_terminal_execution", True):
            if request.tool_name in ["terminal.execute", "shell.execute"] or request.requested_scope in ["terminal.execute", "shell.execute"]:
                return Outcome.BLOCK

        if not self.security_switches.get("enable_desktop_gui_control", True):
            if request.tool_name in ["desktop.click", "desktop.type", "desktop.hotkey", "desktop.drag", "desktop.press"]:
                return Outcome.BLOCK

        if not self.security_switches.get("enable_external_integrations", True):
            if request.tool_name.startswith("gmail.") or request.tool_name.startswith("external."):
                return Outcome.BLOCK

        # 2. Scope-based rule matching
        matched_rules = []
        for rule in self.rules:
            if fnmatch.fnmatch(request.tool_name, rule.scope) or (request.requested_scope and fnmatch.fnmatch(request.requested_scope, rule.scope)):
                matched_rules.append(rule)

        if not matched_rules:
            return Outcome.BLOCK # Secure default if no rules explicitly match

        # Sort by priority descending
        matched_rules.sort(key=lambda r: r.priority, reverse=True)

        highest_priority = matched_rules[0].priority
        top_rules = [r for r in matched_rules if r.priority == highest_priority]

        if len(top_rules) == 1:
            return top_rules[0].outcome

        # Conflict resolution at highest priority tier: BLOCK wins
        outcomes = {r.outcome for r in top_rules}
        if Outcome.BLOCK in outcomes:
            return Outcome.BLOCK
        elif Outcome.APPROVAL in outcomes:
            return Outcome.APPROVAL
        
        return Outcome.ALLOW
