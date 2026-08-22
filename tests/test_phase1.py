import pytest
from datetime import timedelta, datetime
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.agents.templates import Templates
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.core.schemas import RiskTier, ToolRequest, PolicyRule, Outcome, AgentState, AgentType

def test_tool_registry():
    registry = ToolRegistry()
    
    # Register dummy tool with reversibility
    dummy_tool = ToolDefinition(
        name="dummy.tool",
        description="A dummy tool",
        input_schema={},
        output_schema={},
        permissions_required=["dummy.*"],
        risk_level=RiskTier.LOW,
        reversible=True,
        rollback_strategy="undo_dummy",
        rollback_cost="trivial",
        rollback_window="1 hour"
    )
    registry.register_tool(dummy_tool)
    assert registry.get_tool("dummy.tool").reversible is True
    
    # Register file.create_* tools
    formats = ["pdf", "docx", "xlsx", "csv", "json", "pptx", "md"]
    for fmt in formats:
        tool = ToolDefinition(
            name=f"file.create_{fmt}",
            description=f"Create a {fmt} file",
            input_schema={"path": "str", "content": "str"},
            output_schema={"path": "str"},
            permissions_required=["filesystem.write"],
            risk_level=RiskTier.LOW,
            reversible=True,
            rollback_strategy="delete_created_file",
            rollback_cost="trivial",
            rollback_window="unlimited"
        )
        registry.register_tool(tool)
        
    pdf_tool = registry.get_tool("file.create_pdf")
    assert pdf_tool.reversible is True
    assert pdf_tool.rollback_strategy == "delete_created_file"

def test_agent_templates():
    templates = Templates.get_all()
    assert len(templates) == 13
    
    # Verify UniversalFileAgent least privilege
    ufa = Templates.UniversalFileAgent
    assert ufa.permission_scope == ["filesystem.write"]
    assert "filesystem.read" not in ufa.permission_scope
    assert "filesystem.delete" not in ufa.permission_scope

def test_policy_engine():
    engine = DefaultPolicyEngine()
    
    # Setup agent dummy
    agent = AgentState(
        agent_id="test-agent",
        role="test",
        type=AgentType.STATIC,
        goal="test",
        permission_scope=[],
        credential_scope=[],
        tool_scope=[],
        depth=1,
        ttl=timedelta(minutes=5),
        expires_at=datetime.now() + timedelta(minutes=5),
        budget_ref="test-budget"
    )

    # Setup rules
    rules = [
        PolicyRule(rule_id="r1", scope="filesystem.read", condition="", outcome=Outcome.ALLOW, priority=10),
        PolicyRule(rule_id="r2", scope="gmail.send", condition="", outcome=Outcome.APPROVAL, priority=10),
        PolicyRule(rule_id="r3", scope="filesystem.write", condition="", outcome=Outcome.ALLOW, priority=10),
        PolicyRule(rule_id="r4", scope="filesystem.write", condition="", outcome=Outcome.BLOCK, priority=10), # Conflicting
        PolicyRule(rule_id="r5", scope="shell.execute", condition="", outcome=Outcome.BLOCK, priority=20),
    ]
    engine.load_rules(rules)
    
    # Test ALLOW
    req1 = ToolRequest(request_id="req1", agent_id="a1", tool_name="filesystem.read", arguments={}, requested_scope="")
    assert engine.evaluate(req1, agent) == Outcome.ALLOW
    
    # Test APPROVAL
    req2 = ToolRequest(request_id="req2", agent_id="a1", tool_name="gmail.send", arguments={}, requested_scope="")
    assert engine.evaluate(req2, agent) == Outcome.APPROVAL
    
    # Test BLOCK (Higher Priority)
    req3 = ToolRequest(request_id="req3", agent_id="a1", tool_name="shell.execute", arguments={}, requested_scope="")
    assert engine.evaluate(req3, agent) == Outcome.BLOCK
    
    # Test Conflict Resolution (Equal Priority -> BLOCK wins)
    req4 = ToolRequest(request_id="req4", agent_id="a1", tool_name="filesystem.write", arguments={}, requested_scope="")
    assert engine.evaluate(req4, agent) == Outcome.BLOCK
    
    # Test default block (no rule matched)
    req5 = ToolRequest(request_id="req5", agent_id="a1", tool_name="unknown.tool", arguments={}, requested_scope="")
    assert engine.evaluate(req5, agent) == Outcome.BLOCK
