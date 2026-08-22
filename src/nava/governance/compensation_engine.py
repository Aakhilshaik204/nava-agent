import os
import uuid
from pydantic import BaseModel, Field
from typing import Dict, Any
from enum import Enum

from nava.core.llm import get_llm
from langchain_core.messages import SystemMessage, HumanMessage
from nava.core.schemas import Receipt, ToolRequest
from nava.gateway.pipeline import ActionGateway

class CompensatingTool(str, Enum):
    NOTIFY_ADMIN = "mock.notify_admin"
    FLAG_REVIEW = "system.flag_review"

class CompensationDecision(BaseModel):
    tool_name: CompensatingTool = Field(description="The tool to execute to compensate for the failure.")
    arguments: Dict[str, Any] = Field(description="The arguments to pass to the tool.")
    reasoning: str = Field(description="Why this compensating action is required.")

class CompensationEngine:
    def __init__(self, gateway: ActionGateway):
        self.gateway = gateway

    def compensate(self, receipt: Receipt, budget_ref: str):
        """
        Drafts a compensating action for an irreversible tool and routes it through HITL.
        """
        if os.environ.get("NAVA_TEST_MODE") == "1":
            print(f"[CompensationEngine] Test mode: Mock compensation for irreversible tool '{receipt.tool_name}' triggered successfully.")
            return

        llm = get_llm()
        structured_llm = llm.with_structured_output(CompensationDecision)

        sys_msg = SystemMessage(content="You are the Compensation Engine. A task has failed, and an irreversible action must be compensated for. You must choose a compensating tool from your available schema.")
        human_msg = HumanMessage(content=f"Irreversible Action:\nTool: {receipt.tool_name}\nSummary: {receipt.action_summary}\n\nDraft a compensating action.")

        # Charge the LLM cost
        if hasattr(self.gateway, 'budget_engine') and self.gateway.budget_engine:
            self.gateway.budget_engine.consume_internal_llm_call(budget_ref, tokens=300)

        try:
            decision: CompensationDecision = structured_llm.invoke([sys_msg, human_msg])
            print(f"[CompensationEngine] Improvised action: {decision.tool_name.value} — {decision.reasoning}")

            comp_req = ToolRequest(
                request_id=f"cmp-{uuid.uuid4().hex[:8]}",
                agent_id="SYSTEM_COMPENSATION",
                tool_name=decision.tool_name.value,
                arguments=decision.arguments,
                requested_scope="*" # Ideally scoped strictly
            )
            
            # Route through Gateway (this will hit HITL automatically due to policy/risk)
            self.gateway.process_request(comp_req)
            
        except Exception as e:
            print(f"[CompensationEngine] LLM failed to generate a valid compensation (Error: {e}). Triggering hard fallback.")
            self.trigger_hard_fallback(receipt, str(e), budget_ref)

    def compensate_rollback_failure(self, receipt: Receipt, reason: str, budget_ref: str):
        """
        Compensates for the mechanical failure of a rollback.
        """
        print(f"[CompensationEngine] Generating alert for failed rollback of {receipt.tool_name}...")
        comp_req = ToolRequest(
            request_id=f"cmp-{uuid.uuid4().hex[:8]}",
            agent_id="SYSTEM_COMPENSATION",
            tool_name="system.flag_review",
            arguments={
                "reason": f"Rollback failed for {receipt.tool_name}",
                "severity": "CRITICAL"
            },
            requested_scope="system.flag_review"
        )
        self.gateway.process_request(comp_req)

    def trigger_hard_fallback(self, receipt: Receipt, reason: str, budget_ref: str):
        """
        Safe fallback when the LLM itself is unavailable (e.g. rate limit).
        Does NOT use the LLM and does NOT use shell.execute. Uses strict bounded tool.
        """
        comp_req = ToolRequest(
            request_id=f"cmp-{uuid.uuid4().hex[:8]}",
            agent_id="SYSTEM_COMPENSATION",
            tool_name="system.flag_review",
            arguments={
                "reason": f"COMPENSATION_UNAVAILABLE for {receipt.tool_name}. Manual review required. Error: {reason[:100]}",
                "severity": "CRITICAL"
            },
            requested_scope="system.flag_review"
        )
        self.gateway.process_request(comp_req)
