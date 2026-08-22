import pytest
import datetime
import os
import tempfile
from nava.core.schemas import ToolRequest, AgentState, AgentType, RiskTier, RiskDecision, TaskBudget, BudgetStatus, Outcome, Approval, RiskAssessment, ApprovalStatus, MemoryRecord, MemoryTier, MemoryTrustLevel
from nava.governance.risk_engine import DefaultRiskEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.governance.hitl_manager import SingleApprovalManager
from nava.memory.store import ProfileMemoryStore

def test_risk_engine_tiers():
    with tempfile.TemporaryDirectory() as tmpdir:
        profile_path = os.path.join(tmpdir, "profile.json")
        profile_store = ProfileMemoryStore(profile_path)
        
        # Seed Profile Memory
        profile_store.store(MemoryRecord(
            memory_id="1", tier=MemoryTier.PROFILE, content="contact:alice@internal.com", source="user",
            confidence=1.0, importance=1.0, sensitivity="low", trust_level=MemoryTrustLevel.VERIFIED
        ), explicit_user_action=True)
        profile_store.store(MemoryRecord(
            memory_id="2", tier=MemoryTier.PROFILE, content="internal_domain:internal.com", source="user",
            confidence=1.0, importance=1.0, sensitivity="low", trust_level=MemoryTrustLevel.VERIFIED
        ), explicit_user_action=True)

        engine = DefaultRiskEngine(profile_store)
        
        agent = AgentState(
            agent_id="test", role="test", type=AgentType.STATIC, goal="test",
            permission_scope=[], credential_scope=[], tool_scope=[], depth=1,
            ttl=datetime.timedelta(minutes=5),
            expires_at=datetime.datetime.now() + datetime.timedelta(minutes=5),
            budget_ref="test-budget"
        )
        
        # Set deterministic time (12:00 PM) to avoid time-of-day flakiness
        dt_midday = datetime.datetime(2026, 1, 1, 12, 0, 0)

        # LOW risk (0-19)
        req_low = ToolRequest(request_id="1", agent_id="a1", tool_name="t1", arguments={"recipient": "alice@internal.com"}, requested_scope="", created_at=dt_midday)
        risk_low = engine.evaluate(req_low, agent)
        assert risk_low.tier == RiskTier.LOW
        assert risk_low.decision == RiskDecision.AUTO_EXECUTE

        # MEDIUM risk (20-49): Unknown contact (25)
        req_med = ToolRequest(request_id="2", agent_id="a1", tool_name="t1", arguments={"recipient": "unknown@internal.com"}, requested_scope="", created_at=dt_midday)
        risk_med = engine.evaluate(req_med, agent)
        assert risk_med.tier == RiskTier.MEDIUM
        assert risk_med.decision == RiskDecision.NOTIFY
        
        # HIGH risk (50-74): Sensitive file (40) + Attachment (20) = 60
        req_high = ToolRequest(request_id="3", agent_id="a1", tool_name="t1", arguments={"recipient": "alice@internal.com", "attachments": ["secret.pdf"]}, requested_scope="", created_at=dt_midday)
        risk_high = engine.evaluate(req_high, agent)
        assert risk_high.tier == RiskTier.HIGH
        assert risk_high.decision == RiskDecision.HITL
        
        # CRITICAL risk (75+): Sensitive file (40) + External recipient (30) + Unknown contact (25) = 95
        req_crit = ToolRequest(request_id="4", agent_id="a1", tool_name="t1", arguments={"recipient": "stranger@external.com", "attachments": ["secret.pdf"]}, requested_scope="", created_at=dt_midday)
        risk_crit = engine.evaluate(req_crit, agent)
        assert risk_crit.tier == RiskTier.CRITICAL
        assert risk_crit.decision == RiskDecision.BLOCK

def test_risk_context_regression():
    engine = DefaultRiskEngine()
    # Test that the engine's internal checks still accurately flag untrusted entities without a seeded store
    assert engine.is_external_recipient("john@external.com") is True
    assert engine.is_unknown_contact("stranger@internal.com") is True
    assert engine.is_sensitive_file("my_resume_final.pdf") is True

def test_budget_engine():
    engine = DefaultBudgetEngine()
    agent = AgentState(
        agent_id="test", role="test", type=AgentType.STATIC, goal="test",
        permission_scope=[], credential_scope=[], tool_scope=[], depth=1,
        ttl=datetime.timedelta(minutes=5),
        expires_at=datetime.datetime.now() + datetime.timedelta(minutes=5),
        budget_ref="test-budget"
    )
    budget = TaskBudget(task_id="test-budget", max_agents=10, max_depth=3, max_steps=100, max_tokens=1000, max_runtime=datetime.timedelta(minutes=30), max_retries=5)
    engine.register_budget(budget)

    req = ToolRequest(request_id="1", agent_id="a1", tool_name="t1", arguments={}, requested_scope="")
    
    # OK (50%)
    budget.consumed_steps = 49
    assert engine.check_and_consume(req, agent) is True
    assert budget.status == BudgetStatus.OK
    
    # WARNING_80 (80%)
    budget.consumed_steps = 79
    assert engine.check_and_consume(req, agent) is True
    assert budget.status == BudgetStatus.WARNING_80
    
    # RESTRICTED_90 (90%)
    budget.consumed_steps = 89
    assert engine.check_and_consume(req, agent) is True
    assert budget.status == BudgetStatus.RESTRICTED_90
    
    # EXHAUSTED (100%)
    budget.consumed_steps = 99
    assert engine.check_and_consume(req, agent) is False
    assert budget.status == BudgetStatus.EXHAUSTED

def test_hitl_manager():
    manager = SingleApprovalManager()
    req = ToolRequest(request_id="1", agent_id="a1", tool_name="t1", arguments={}, requested_scope="")
    
    # LOW
    risk = RiskAssessment(assessment_id="1", tool_request_id="1", total_score=10, tier=RiskTier.LOW, decision=RiskDecision.AUTO_EXECUTE)
    assert manager.decide(req, risk) == Outcome.ALLOW
    
    # MEDIUM (auto-executes but flagged for notify in future)
    risk = RiskAssessment(assessment_id="2", tool_request_id="1", total_score=30, tier=RiskTier.MEDIUM, decision=RiskDecision.NOTIFY)
    assert manager.decide(req, risk) == Outcome.ALLOW
    
    # HIGH -> Returns Approval object
    risk = RiskAssessment(assessment_id="3", tool_request_id="1", total_score=70, tier=RiskTier.HIGH, decision=RiskDecision.HITL)
    res = manager.decide(req, risk)
    assert isinstance(res, Approval)
    assert res.status == ApprovalStatus.PENDING
    
    # CRITICAL -> Hard BLOCK
    risk = RiskAssessment(assessment_id="4", tool_request_id="1", total_score=80, tier=RiskTier.CRITICAL, decision=RiskDecision.BLOCK)
    assert manager.decide(req, risk) == Outcome.BLOCK
