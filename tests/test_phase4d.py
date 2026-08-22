import pytest
import os
import tempfile
import yaml
import datetime
from nava.core.boot import NavaBootstrapper
from nava.core.schemas import AgentSpec, AgentState, AgentType
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.tools.registry import ToolRegistry
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.agents.factory import AgentFactory

def test_phase4d_bootstrapper():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "nava.yaml")
        config_data = {
            "root_agent": {
                "ceiling_permissions": ["filesystem.write", "github.read"],
                "ceiling_tools": ["file.write"]
            },
            "budget": {
                "max_agents": 10,
                "max_depth": 3
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
            
        boot = NavaBootstrapper(config_path)
        root, budget = boot.bootstrap()
        
        assert root.role == "Nava"
        assert "filesystem.write" in root.permission_scope
        assert "github.read" in root.permission_scope
        assert "file.write" in root.tool_scope
        assert root.depth == 0
        
        assert budget.max_agents == 10
        assert budget.max_depth == 3

def test_phase4d_runaway_loop_protection():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "nava.yaml")
        config_data = {
            "root_agent": {
                "ceiling_permissions": ["filesystem.write"],
                "ceiling_tools": ["file.write"]
            },
            "budget": {
                "max_agents": 2, # STRICT LIMIT
                "max_depth": 5
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
            
        boot = NavaBootstrapper(config_path)
        root, budget = boot.bootstrap()
        
        registry = ToolRegistry()
        policy = DefaultPolicyEngine()
        budget_engine = DefaultBudgetEngine()
        budget_engine.register_budget(budget)
        
        factory = AgentFactory(registry, policy, budget_engine)
        
        spec1 = AgentSpec(
            request_id="req-1", requested_role="DocumentAgent", goal="G1",
            parent_agent_id=root.agent_id, requested_tools=[], requested_permission_scope=[],
            ttl=datetime.timedelta(minutes=5), max_steps=5, max_tokens=100, max_children=2, dedup_hash="1"
        )
        
        spec2 = AgentSpec(
            request_id="req-2", requested_role="DocumentAgent", goal="G2",
            parent_agent_id=root.agent_id, requested_tools=[], requested_permission_scope=[],
            ttl=datetime.timedelta(minutes=5), max_steps=5, max_tokens=100, max_children=2, dedup_hash="2"
        )
        
        spec3 = AgentSpec(
            request_id="req-3", requested_role="DocumentAgent", goal="G3",
            parent_agent_id=root.agent_id, requested_tools=[], requested_permission_scope=[],
            ttl=datetime.timedelta(minutes=5), max_steps=5, max_tokens=100, max_children=2, dedup_hash="3"
        )
        
        # 1st agent should spawn fine (consumed_agents = 1)
        child1 = factory.spawn_agent(spec1, root)
        assert child1 is not None
        
        # 2nd agent should spawn fine (consumed_agents = 2)
        child2 = factory.spawn_agent(spec2, root)
        assert child2 is not None
        
        # 3rd agent should FAIL due to budget.max_agents = 2
        with pytest.raises(RuntimeError) as exc:
            factory.spawn_agent(spec3, root)
            
        assert "Budget exhausted for spawning new agents" in str(exc.value)

def test_phase4d_max_depth_protection():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "nava.yaml")
        config_data = {
            "root_agent": {
                "ceiling_permissions": [],
                "ceiling_tools": []
            },
            "budget": {
                "max_agents": 100,
                "max_depth": 1 # STRICT DEPTH LIMIT
            }
        }
        with open(config_path, "w") as f:
            yaml.dump(config_data, f)
            
        boot = NavaBootstrapper(config_path)
        root, budget = boot.bootstrap()
        
        registry = ToolRegistry()
        policy = DefaultPolicyEngine()
        budget_engine = DefaultBudgetEngine()
        budget_engine.register_budget(budget)
        
        factory = AgentFactory(registry, policy, budget_engine)
        
        spec = AgentSpec(
            request_id="req-1", requested_role="DocumentAgent", goal="G1",
            parent_agent_id=root.agent_id, requested_tools=[], requested_permission_scope=[],
            ttl=datetime.timedelta(minutes=5), max_steps=5, max_tokens=100, max_children=5, dedup_hash="1"
        )
        
        # Root is depth 0. Spawning depth 1 should be OK (if parent_depth < max_depth)
        # parent.depth (0) < max_depth (1).
        child1 = factory.spawn_agent(spec, root)
        
        # child1 is depth 1. Spawning from child1 should fail, since child1.depth (1) >= max_depth (1)
        with pytest.raises(RuntimeError) as exc:
            factory.spawn_agent(spec, child1)
            
        assert "Budget exhausted for spawning new agents" in str(exc.value)
