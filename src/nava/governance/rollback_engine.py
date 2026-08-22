import json
from typing import List, Optional
import uuid

from nava.core.schemas import Receipt, ToolRequest, ResultEnum
from nava.gateway.pipeline import ActionGateway

class RollbackEngine:
    def __init__(self, gateway: ActionGateway, compensation_engine: Optional['CompensationEngine'] = None):
        self.gateway = gateway
        self.compensation_engine = compensation_engine

    def rollback(self, receipts: List[Receipt], budget_ref: str) -> bool:
        """
        Iterates backward through the provided receipts and deterministically undoes them.
        Returns True if the entire chain was successfully rolled back, False otherwise.
        """
        success_chain = True
        
        for receipt in reversed(receipts):
            # Only rollback successful mutating actions
            if receipt.result != ResultEnum.SUCCESS:
                continue

            tool_def = self.gateway.registry.get_tool(receipt.tool_name)
            
            if tool_def.reversible:
                # Dynamically construct inverse request
                inverse_req = self._construct_inverse(receipt)
                if not inverse_req:
                    print(f"[RollbackEngine] Warning: Could not construct inverse for {receipt.tool_name}")
                    self._log_rollback_failed(receipt, budget_ref, "Missing inverse construction logic")
                    success_chain = False
                    continue

                try:
                    inverse_req.agent_id = "SYSTEM_ROLLBACK"
                    # Using the root budget or a cleanup allowance
                    # (Budget checking logic is handled within gateway if SYSTEM_ROLLBACK is exempted)
                    
                    print(f"[RollbackEngine] Executing inverse for {receipt.tool_name}...")
                    rollback_receipt = self.gateway.process_request(inverse_req)
                    
                    if rollback_receipt.result != ResultEnum.SUCCESS:
                        self._log_rollback_failed(receipt, budget_ref, f"Inverse tool execution failed: {rollback_receipt.result_data}")
                        success_chain = False
                except Exception as e:
                    self._log_rollback_failed(receipt, budget_ref, str(e))
                    success_chain = False
            else:
                # Action is irreversible
                print(f"[RollbackEngine] Found irreversible action {receipt.tool_name}. Delegating to Compensation Engine...")
                self._log_compensation_unavailable(receipt, budget_ref)
                if self.compensation_engine:
                    try:
                        self.compensation_engine.compensate(receipt, budget_ref)
                    except Exception as e:
                        print(f"[CompensationEngine] Failed to generate compensation: {e}")
                        self._log_compensation_failed(receipt, budget_ref, str(e))
                        success_chain = False
                else:
                    self._log_compensation_failed(receipt, budget_ref, "No compensation engine available")
                    success_chain = False

        if not success_chain:
            print("\n[!] CRITICAL: Rollback encountered partial failures. Workspace may be in a corrupted state.")
            
        return success_chain

    def _construct_inverse(self, receipt: Receipt) -> Optional[ToolRequest]:
        if receipt.tool_name in ["file.write", "code.replace_content"]:
            # Need to find the pre_snapshot_id
            obs = receipt.result_data.get("_observation", {}) if isinstance(receipt.result_data, dict) else {}
            pre_content_path = obs.get("pre_content")
            resource = obs.get("pre_resource")

            if resource:
                if pre_content_path:
                    # Restore from snapshot
                    with open(pre_content_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    return ToolRequest(
                        request_id=f"rbk-{uuid.uuid4().hex[:8]}",
                        agent_id="SYSTEM_ROLLBACK",
                        tool_name="file.write",
                        arguments={
                            "filename": resource,
                            "content": content,
                            "overwrite": True
                        },
                        requested_scope="filesystem.write"
                    )
                else:
                    # File didn't exist, inverse is delete
                    return ToolRequest(
                        request_id=f"rbk-{uuid.uuid4().hex[:8]}",
                        agent_id="SYSTEM_ROLLBACK",
                        tool_name="file.delete",
                        arguments={
                            "filename": resource
                        },
                        requested_scope="filesystem.write"
                    )
        return None

    def _log_rollback_failed(self, receipt: Receipt, budget_ref: str, reason: str):
        # We would log a distinct ROLLBACK_FAILED event/receipt
        print(f"[RollbackEngine] ROLLBACK_FAILED for receipt {receipt.receipt_id}: {reason}")
        # Route mechanical failures to the CompensationEngine
        if self.compensation_engine:
            self.compensation_engine.compensate_rollback_failure(receipt, reason, budget_ref)
            
    def _log_compensation_unavailable(self, receipt: Receipt, budget_ref: str):
        print(f"[RollbackEngine] COMPENSATION_UNAVAILABLE for receipt {receipt.receipt_id}")

    def _log_compensation_failed(self, receipt: Receipt, budget_ref: str, reason: str):
        print(f"[CompensationEngine] COMPENSATION_FAILED for receipt {receipt.receipt_id}: {reason}")
        # Do NOT route to the compensation LLM since it just failed! 
        # Directly construct a safe fallback notification without an LLM.
        if self.compensation_engine:
            self.compensation_engine.trigger_hard_fallback(receipt, reason, budget_ref)
