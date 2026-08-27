import os
import unittest
import tempfile
import shutil
from datetime import datetime, timedelta
from nava.tools.executor import LocalToolExecutor
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.core.schemas import ToolRequest, RiskTier, AgentSpec, AgentState, AgentType, Priority
from nava.agents.factory import AgentFactory
from nava.governance.policy_engine import DefaultPolicyEngine
from nava.governance.budget_engine import DefaultBudgetEngine

class TestDocumentAgentMCP(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        self.executor = LocalToolExecutor()
        self.executor.set_active_task("tsk_test_doc")
        
        self.registry = ToolRegistry()
        for t_name, scope in [
            ("typst.compile_pdf", "document.compile"),
            ("typst.render_template", "document.compile"),
            ("doc.read_document", "document.read"),
            ("file.write", "filesystem.write"),
            ("file.read", "filesystem.read")
        ]:
            self.registry.register_tool(ToolDefinition(
                name=t_name,
                description=f"Test tool {t_name}",
                input_schema={},
                output_schema={},
                permissions_required=[scope],
                risk_level=RiskTier.LOW,
                reversible=True
            ))
        
        self.policy_engine = DefaultPolicyEngine()
        self.budget_engine = DefaultBudgetEngine()
        self.factory = AgentFactory(self.registry, self.policy_engine, self.budget_engine)

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_typst_compile_pdf(self):
        typst_code = """
#set page(paper: "a4", margin: 2cm)
#set text(font: "Helvetica", size: 12pt)

= NAVA Autonomous Governance
This document demonstrates Typst vector compilation in NAVA Agent.

== Key Principles
- Deterministic Policy Engine
- Cryptographic Execution Receipts
- Ephemeral Lifecycle Teardown
"""
        req = ToolRequest(
            request_id="req-typ-1",
            agent_id="agt-doc-1",
            tool_name="typst.compile_pdf",
            arguments={
                "source": typst_code,
                "output_pdf": "governance_spec.pdf"
            },
            requested_scope="document.compile"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False), msg=f"Compilation failed: {res}")
        self.assertGreater(res.get("bytes_written", 0), 100)
        self.assertTrue(os.path.exists("tasks/tsk_test_doc/artifacts/governance_spec.pdf") or os.path.exists(res.get("saved_to", "")))

    def test_typst_render_template(self):
        req = ToolRequest(
            request_id="req-tmpl-1",
            agent_id="agt-doc-1",
            tool_name="typst.render_template",
            arguments={
                "template_name": "executive_report",
                "title": "Quarterly Autonomous Agent Performance",
                "author": "DocumentAgent",
                "content_blocks": [
                    {
                        "type": "paragraph",
                        "title": "Executive Summary",
                        "content": "All autonomous workflows met the SLA targets across all 4 operational quarters."
                    },
                    {
                        "type": "callout",
                        "content": "Zero governance bypass incidents observed during the active period."
                    },
                    {
                        "type": "table",
                        "headers": ["Quarter", "Tasks Completed", "Success Rate"],
                        "rows": [
                            ["Q1", "1,240", "99.8%"],
                            ["Q2", "1,850", "99.9%"],
                            ["Q3", "2,100", "100.0%"],
                            ["Q4", "2,600", "99.9%"]
                        ]
                    }
                ],
                "output_pdf": "executive_performance_report.pdf"
            },
            requested_scope="document.compile"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False), msg=f"Render template failed: {res}")
        self.assertGreater(res.get("bytes_written", 0), 100)

    def test_doc_read_document(self):
        test_file = os.path.join(self.temp_dir, "notes.md")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("# Meeting Notes\nDiscussion on multi-agent consensus mechanisms.")
            
        req = ToolRequest(
            request_id="req-read-1",
            agent_id="agt-doc-1",
            tool_name="doc.read_document",
            arguments={"file_path": test_file},
            requested_scope="document.read"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        self.assertEqual(res.get("format"), ".md")
        self.assertIn("consensus", res.get("content", ""))

    def test_role_restrictions_allow_document_and_universal_file_agents(self):
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
        
        # 1. DocumentAgent requesting typst.compile_pdf -> MUST SUCCEED
        spec_doc = AgentSpec(
            request_id="spec-doc-1",
            requested_role="DocumentAgent",
            goal="Compile technical report",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["document.compile", "document.read", "typst.*", "doc.*"],
            requested_tools=["typst.compile_pdf", "typst.render_template"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-doc-1"
        )
        agent_doc = self.factory.spawn_agent(spec_doc, parent_state)
        self.assertIn("typst.compile_pdf", agent_doc.tool_scope)
        self.assertIn("typst.render_template", agent_doc.tool_scope)
        
        # 2. UniversalFileAgent requesting typst.compile_pdf -> MUST SUCCEED
        spec_uf = AgentSpec(
            request_id="spec-uf-1",
            requested_role="UniversalFileAgent",
            goal="Generate document files",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["filesystem.write", "filesystem.read", "document.compile", "typst.*"],
            requested_tools=["typst.compile_pdf", "file.write"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-uf-1"
        )
        agent_uf = self.factory.spawn_agent(spec_uf, parent_state)
        self.assertIn("typst.compile_pdf", agent_uf.tool_scope)
        
        # 3. CodingAgent or ResearchAgent requesting typst.compile_pdf -> MUST BE STRIPPED
        spec_coding = AgentSpec(
            request_id="spec-code-1",
            requested_role="CodingAgent",
            goal="Write python code",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["filesystem.write", "document.compile"],
            requested_tools=["typst.compile_pdf", "file.write"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-code-1"
        )
        agent_coding = self.factory.spawn_agent(spec_coding, parent_state)
        self.assertNotIn("typst.compile_pdf", agent_coding.tool_scope)

    def test_cross_task_artifact_continuity(self):
        # 1. Task 1 creates governance_spec.typ
        self.executor.set_active_task("tsk_task_1")
        req1 = ToolRequest(
            request_id="req-c1",
            agent_id="agt-1",
            tool_name="file.write",
            arguments={"filename": "governance_spec.typ", "content": "= Autonomous AI Governance\nZero-trust execution specification."},
            requested_scope="filesystem.write"
        )
        self.executor.execute(req1)
        
        # 2. Task 2 reads governance_spec.typ (must resolve from Task 1 seamlessly)
        self.executor.set_active_task("tsk_task_2")
        req2 = ToolRequest(
            request_id="req-c2",
            agent_id="agt-2",
            tool_name="file.read",
            arguments={"filename": "governance_spec.typ"},
            requested_scope="filesystem.read"
        )
        res2 = self.executor.execute(req2)
        self.assertIn("content", res2)
        self.assertIn("Autonomous AI Governance", res2["content"])

if __name__ == "__main__":
    unittest.main()
