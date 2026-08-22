from typing import Optional, Union, Tuple
from nava.core.schemas import ToolRequest, RiskAssessment, Approval, ApprovalStatus, Outcome, RiskTier
from nava.gateway.pipeline import HITLManager
import uuid

class SingleApprovalManager(HITLManager):
    """
    Manages human-in-the-loop interventions (single, unbatched logic).
    """
    def __init__(self):
        self.pending_approvals = {}

    def decide(self, request: ToolRequest, risk: RiskAssessment) -> Union[Outcome, Approval]:
        """
        Determines whether a tool execution requires human approval.
        Returns:
            Outcome.ALLOW if it can auto-execute.
            Outcome.BLOCK if it's too dangerous to even ask (CRITICAL).
            Approval object if it requires HITL (HIGH).
            Note: For MEDIUM, it returns ALLOW but would be tagged for a dashboard.
        """
        if risk.tier == RiskTier.LOW:
            return Outcome.ALLOW
            
        elif risk.tier == RiskTier.MEDIUM:
            # Phase 8: Notification logic goes here.
            # For now, it auto-executes.
            return Outcome.ALLOW
            
        elif risk.tier == RiskTier.HIGH:
            # Requires HITL
            approval = Approval(
                approval_id="app_" + str(uuid.uuid4())[:8],
                tool_request_ids=[request.request_id],
                group_key=f"{request.tool_name}_{request.arguments.get('recipient', 'unknown')}",
                combined_risk_tier=RiskTier.HIGH,
                status=ApprovalStatus.PENDING
            )
            self.pending_approvals[approval.approval_id] = approval
            return approval
            
        elif risk.tier == RiskTier.CRITICAL:
            # Hard block - never present to the user.
            return Outcome.BLOCK
            
        return Outcome.BLOCK # Failsafe fallback

    def request_approval(self, tool_request: ToolRequest, assessment: Optional[RiskAssessment] = None, context: str = "") -> Approval:
        """
        Explicitly requests human approval for a tool invocation or escalation context.
        """
        approval = Approval(
            approval_id="app_" + str(uuid.uuid4())[:8],
            tool_request_ids=[tool_request.request_id] if tool_request else [],
            group_key=f"{tool_request.tool_name if tool_request else 'system'}_{context[:20]}",
            combined_risk_tier=assessment.tier if assessment else RiskTier.HIGH,
            status=ApprovalStatus.PENDING
        )
        self.pending_approvals[approval.approval_id] = approval
        return approval

    def cancel_all_pending(self) -> int:
        """
        Emergency Kill Switch (Section 31.4):
        Cancels all pending approvals immediately.
        """
        count = len(self.pending_approvals)
        for app in self.pending_approvals.values():
            app.status = ApprovalStatus.REJECTED
        self.pending_approvals.clear()
        print(f"[SingleApprovalManager] EMERGENCY STOP: Cancelled {count} pending approvals.")
        return count


