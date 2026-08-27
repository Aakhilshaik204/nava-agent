import unittest
import os
import shutil
import tempfile
from datetime import datetime, timedelta

from nava.tools.registry import ToolRegistry
from nava.tools.tool_manifest import get_default_tools
from nava.tools.executor import LocalToolExecutor
from nava.core.schemas import ToolRequest, AgentState, AgentSpec, AgentType, Priority
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine
from nava.agents.factory import AgentFactory
from nava.agents.templates import Templates, StaticAgentTemplate

class TestReviewerVerifierMCP(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.registry = ToolRegistry()
        for tool_def in get_default_tools():
            self.registry.register_tool(tool_def)
            
        self.executor = LocalToolExecutor(registry=self.registry)
        self.policy_engine = DefaultPolicyEngine()
        self.budget_engine = DefaultBudgetEngine()
        self.factory = AgentFactory(self.registry, self.policy_engine, self.budget_engine)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sequential_thinking_step(self):
        # 1. First reasoning thought
        req1 = ToolRequest(
            request_id="req-seq-1",
            agent_id="agt-rev-1",
            tool_name="sequential_thinking.step",
            arguments={
                "thought": "Initial hypothesis: The AST tree in parser.py does not handle string escapes correctly.",
                "thought_number": 1,
                "total_thoughts": 3,
                "next_thought_needed": True,
                "confidence_score": 0.8
            },
            requested_scope="reasoning.sequential"
        )
        res1 = self.executor.execute(req1)
        self.assertTrue(res1.get("success", False))
        self.assertEqual(res1.get("recorded_thought_number"), 1)
        self.assertEqual(res1.get("active_branch"), "main")

        # 2. Branching thought
        req2 = ToolRequest(
            request_id="req-seq-2",
            agent_id="agt-rev-1",
            tool_name="sequential_thinking.step",
            arguments={
                "thought": "Alternative branch: What if the issue is in the lexer token buffer rather than AST parser?",
                "thought_number": 2,
                "total_thoughts": 3,
                "branch_from_thought": 1,
                "branch_id": "branch-lexer-hypothesis",
                "next_thought_needed": False,
                "confidence_score": 0.95
            },
            requested_scope="reasoning.sequential"
        )
        res2 = self.executor.execute(req2)
        self.assertTrue(res2.get("success", False))
        self.assertEqual(res2.get("active_branch"), "branch-lexer-hypothesis")

    def test_audit_verify_invariants(self):
        # 1. Valid Scope Alignment (child ⊆ parent)
        req_valid = ToolRequest(
            request_id="req-inv-1",
            agent_id="agt-ver-1",
            tool_name="audit.verify_invariants",
            arguments={
                "check_scopes": {
                    "parent_scope": ["filesystem.read", "test.run", "audit.verify"],
                    "child_scope": ["filesystem.read", "audit.verify"]
                }
            },
            requested_scope="audit.verify"
        )
        res_valid = self.executor.execute(req_valid)
        self.assertTrue(res_valid.get("success", False))
        self.assertEqual(len(res_valid.get("violations", [])), 0)

        # 2. Scope Escalation Violation (child attempts unauthorized scope)
        req_invalid = ToolRequest(
            request_id="req-inv-2",
            agent_id="agt-ver-1",
            tool_name="audit.verify_invariants",
            arguments={
                "check_scopes": {
                    "parent_scope": ["filesystem.read"],
                    "child_scope": ["filesystem.read", "terminal.execute", "shell.execute"]
                }
            },
            requested_scope="audit.verify"
        )
        res_invalid = self.executor.execute(req_invalid)
        self.assertFalse(res_invalid.get("success", True))
        self.assertGreater(len(res_invalid.get("violations", [])), 0)
        self.assertEqual(res_invalid["violations"][0]["severity"], "CRITICAL")

    def test_audit_security_scan(self):
        # 1. Vulnerable Python file with eval() and secret
        vuln_file = os.path.join(self.test_dir, "vulnerable_code.py")
        with open(vuln_file, "w", encoding="utf-8") as f:
            f.write(
                "import os\n"
                "api_key = 'ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'\n"
                "def execute_user_code(user_input):\n"
                "    return eval(user_input)\n"
            )

        req_vuln = ToolRequest(
            request_id="req-sec-1",
            agent_id="agt-rev-1",
            tool_name="audit.security_scan",
            arguments={"filename": vuln_file},
            requested_scope="audit.security"
        )
        res_vuln = self.executor.execute(req_vuln)
        self.assertTrue(res_vuln.get("success", False))
        self.assertFalse(res_vuln.get("is_clean", True))
        self.assertEqual(res_vuln.get("verdict"), "VULNERABILITIES_DETECTED")
        
        types = [find["type"] for find in res_vuln.get("findings", [])]
        self.assertIn("DANGEROUS_EXECUTION", types)
        self.assertIn("HARDCODED_SECRET", types)

        # 2. Clean Python file
        clean_file = os.path.join(self.test_dir, "clean_code.py")
        with open(clean_file, "w", encoding="utf-8") as f:
            f.write(
                "def add_numbers(a: int, b: int) -> int:\n"
                "    return a + b\n"
            )
            
        req_clean = ToolRequest(
            request_id="req-sec-2",
            agent_id="agt-rev-1",
            tool_name="audit.security_scan",
            arguments={"filename": clean_file},
            requested_scope="audit.security"
        )
        res_clean = self.executor.execute(req_clean)
        self.assertTrue(res_clean.get("success", False))
        self.assertTrue(res_clean.get("is_clean", False))
        self.assertEqual(res_clean.get("verdict"), "PASSED")

    def test_audit_verify_grounding(self):
        # 1. Create sample dataset
        csv_file = os.path.join(self.test_dir, "benchmark_metrics.csv")
        with open(csv_file, "w", encoding="utf-8") as f:
            f.write("Model,Throughput,Latency,Cost\nvLLM,1250,14.2,0.002\nOllama,620,28.5,0.001\nSGLang,1420,11.8,0.0018\n")

        # 2. Create executive report referencing dataset figures
        rep_file = os.path.join(self.test_dir, "benchmark_summary.md")
        with open(rep_file, "w", encoding="utf-8") as f:
            f.write("# LLM Engine Benchmark Report\nEvaluated 3 models across Throughput, Latency, and Cost metrics.\n")

        req_ground = ToolRequest(
            request_id="req-ground-1",
            agent_id="agt-ver-1",
            tool_name="audit.verify_grounding",
            arguments={"report_path": rep_file, "data_source_path": csv_file},
            requested_scope="audit.verify"
        )
        res_ground = self.executor.execute(req_ground)
        self.assertTrue(res_ground.get("success", False))
        self.assertEqual(res_ground.get("verdict"), "GROUNDED_ACCURATE")
        self.assertGreaterEqual(res_ground.get("grounding_score", 0), 0.8)

    def test_role_restrictions_allow_reviewer_and_verifier_agents(self):
        parent_state = AgentState(
            agent_id="agt-root",
            role="RootAgent",
            type=AgentType.STATIC,
            goal="Manage system",
            permission_scope=["*"],
            credential_scope=["*"],
            tool_scope=["*"],
            depth=0,
            ttl=timedelta(minutes=10),
            expires_at=datetime.utcnow() + timedelta(minutes=10),
            budget_ref="bgt-1"
        )

        # 1. ReviewerAgent requesting audit.security_scan & sequential_thinking.step -> MUST SUCCEED
        spec_rev = AgentSpec(
            request_id="spec-rev-1",
            requested_role="ReviewerAgent",
            goal="Review code security",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["reasoning.sequential", "audit.security", "sequential_thinking.*", "audit.*"],
            requested_tools=["sequential_thinking.step", "audit.security_scan"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-rev-1"
        )
        agent_rev = self.factory.spawn_agent(spec_rev, parent_state)
        self.assertIn("sequential_thinking.step", agent_rev.tool_scope)
        self.assertIn("audit.security_scan", agent_rev.tool_scope)

        # 2. VerifierAgent requesting audit.verify_invariants -> MUST SUCCEED
        spec_ver = AgentSpec(
            request_id="spec-ver-1",
            requested_role="VerifierAgent",
            goal="Verify invariants",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["audit.verify", "audit.*"],
            requested_tools=["audit.verify_invariants", "audit.verify_grounding"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-ver-1"
        )
        agent_ver = self.factory.spawn_agent(spec_ver, parent_state)
        self.assertIn("audit.verify_invariants", agent_ver.tool_scope)
        self.assertIn("audit.verify_grounding", agent_ver.tool_scope)

        # 3. CodingAgent requesting audit.security_scan -> MUST BE STRIPPED
        spec_coding = AgentSpec(
            request_id="spec-code-1",
            requested_role="CodingAgent",
            goal="Write code",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["filesystem.write", "audit.security"],
            requested_tools=["audit.security_scan", "file.write"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-code-1"
        )
        agent_coding = self.factory.spawn_agent(spec_coding, parent_state)
        self.assertNotIn("audit.security_scan", agent_coding.tool_scope)

if __name__ == "__main__":
    unittest.main()
