import os
import unittest
import tempfile
import shutil
from nava.tools.presentation_engine import PresentationEngine
from nava.tools.executor import LocalToolExecutor
from nava.core.schemas import ToolRequest


class TestPresentationEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        self.engine = PresentationEngine(
            path_resolver=lambda p: os.path.abspath(p),
            sanitizer=lambda p: os.path.abspath(p),
            artifact_resolver=lambda p: os.path.abspath(p)
        )
        self.executor = LocalToolExecutor()
        self.executor.set_active_task("tsk_presentation_test")

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_standalone_html_generation(self):
        """Tests Gamma-style interactive HTML5 presentation deck generation."""
        slides = [
            {
                "title": "Autonomous Agent Architecture",
                "subtitle": "High-throughput deterministic tool routing",
                "badge": "ARCHITECTURE",
                "layout": "cards_3",
                "cards": [
                    {"title": "Policy Engine", "content": "Zero-trust sandbox validation with AST inspection.", "tag": "CORE"},
                    {"title": "Budget Ledger", "content": "Deterministic token and step quotas.", "tag": "GOVERNANCE"},
                    {"title": "Subagent Dispatch", "content": "Parallel fan-out execution tree.", "tag": "ORCHESTRATION"}
                ]
            },
            {
                "title": "Performance Benchmarks",
                "subtitle": "Measured enterprise improvements across 500 tasks",
                "badge": "METRICS",
                "layout": "metrics_3",
                "metrics": [
                    {"value": "99.4%", "label": "Accuracy", "subtext": "Grounding verification score"},
                    {"value": "4.8x", "label": "Speedup", "subtext": "Parallel execution latency reduction"},
                    {"value": "0.00%", "label": "Policy Violations", "subtext": "Enforced by Gateway"}
                ]
            }
        ]

        html_output = self.engine.generate_standalone_html(
            title="NAVA Intelligence Briefing",
            slides=slides,
            theme_name="dark_executive",
            author="NAVA Test Agent"
        )

        self.assertIn("NAVA Intelligence Briefing", html_output)
        self.assertIn("Autonomous Agent Architecture", html_output)
        self.assertIn("99.4%", html_output)
        self.assertIn("slide-indicator", html_output)
        self.assertIn("progress-bar", html_output)

    def test_render_template_html_and_md(self):
        """Tests rendering pre-designed presentation template to files."""
        slides = [
            {
                "title": "Next-Gen AI Workspace",
                "badge": "VISION",
                "layout": "card_grid",
                "cards": [
                    {"title": "Modular Tools", "content": "Dynamic MCP discovery and injection."},
                    {"title": "Safety Switches", "content": "Instant kill-switch enforcement."}
                ]
            },
            {
                "title": "Key Indicators",
                "badge": "KPI",
                "layout": "metrics",
                "metrics": [
                    {"value": "12.5k", "label": "Tasks Run"},
                    {"value": "99.9%", "label": "Uptime"}
                ]
            }
        ]

        res = self.engine.render_template(
            template_name="dark_executive",
            title="Q3 Strategy Presentation",
            slides=slides,
            output_path="test_deck.html",
            author="Strategic Agent"
        )

        self.assertTrue(res.get("success"))
        self.assertEqual(res.get("total_slides"), 3) # Cover + 2 slides
        self.assertTrue(os.path.exists("test_deck.html"))
        self.assertTrue(os.path.exists("test_deck.md"))

        with open("test_deck.md", "r", encoding="utf-8") as f:
            md_content = f.read()
            self.assertIn("Q3 Strategy Presentation", md_content)
            self.assertIn("Next-Gen AI Workspace", md_content)
            self.assertIn("bg-gradient-to-r", md_content)

    def test_compile_slidev_source(self):
        """Tests compiling raw Slidev markdown markup."""
        raw_slidev = """---
theme: default
background: '#0F172A'
class: 'text-white p-10'
---

# Enterprise AI Orchestration
<p class="text-slate-400">Quarterly Roadmap & Deliverables</p>

---
background: '#0F172A'
class: 'text-white p-10'
---

## Core Pillars
<div class="grid grid-cols-2 gap-4">
  <div class="p-4 bg-slate-800 rounded-xl">Autonomous Graph Execution</div>
  <div class="p-4 bg-slate-800 rounded-xl">Deterministic State Persistence</div>
</div>
"""
        res = self.engine.compile_slidev(
            source=raw_slidev,
            output_path="compiled_deck.html",
            format_type="html"
        )

        self.assertTrue(res.get("success"))
        self.assertTrue(os.path.exists("compiled_deck.html"))
        self.assertTrue(os.path.exists("compiled_deck.md"))

    def test_tool_executor_presentation_render_template(self):
        """Tests ToolExecutor dispatch for presentation.render_template."""
        req = ToolRequest(
            tool="presentation.render_template",
            arguments={
                "template_name": "pitch_deck",
                "title": "NAVA OS Series A",
                "slides": [
                    {
                        "title": "The Problem & Solution",
                        "layout": "two_column",
                        "left_content": "Current agents lack deterministic governance.",
                        "right_content": "NAVA provides end-to-end cryptographic verifiability."
                    }
                ],
                "output_path": "nava_pitch.html"
            }
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success"))
        self.assertIn("nava_pitch.html", res.get("saved_to"))

    def test_tool_executor_presentation_create_slidev(self):
        """Tests ToolExecutor dispatch for presentation.create_slidev."""
        req = ToolRequest(
            tool="presentation.create_slidev",
            arguments={
                "source": "# Slidev Test\n\n---\n\n## Slide Two\n- Item 1\n- Item 2",
                "output_path": "slidev_output.html",
                "format": "html"
            }
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success"))
        self.assertIn("slidev_output.html", res.get("saved_to"))


if __name__ == "__main__":
    unittest.main()
