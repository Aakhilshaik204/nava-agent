import os
import sys
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock, patch

os.environ["NAVA_TEST_MODE"] = "1"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from nava.ui.terminal import TerminalTheme, BoxRenderer, AgentTreeVisualizer
from nava.ui.cowork_tui import CoworkTUI
from nava.orchestrator import Orchestrator
from nava.skills.manager import SkillManager

class TestCoworkUI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_terminal_theme_and_badges(self):
        """Verify role badges and status styling."""
        badge = TerminalTheme.badge("CodingAgent")
        self.assertIn("CodingAgent", badge)
        
        status_ok = TerminalTheme.status_badge("SUCCESS")
        self.assertIn("SUCCESS", status_ok)
        
        status_err = TerminalTheme.status_badge("BLOCKED")
        self.assertIn("BLOCKED", status_err)

    def test_box_renderer_panels_and_tables(self):
        """Verify Unicode box panel and table layout rendering."""
        panel = BoxRenderer.render_panel("TEST PANEL", ["Line 1 content", "Line 2 content"], width=60)
        self.assertIn("TEST PANEL", panel)
        self.assertIn("Line 1 content", panel)
        self.assertIn("╭─", panel)
        self.assertIn("╰─", panel)

        table = BoxRenderer.render_table(["Col A", "Col B"], [["Val 1", "Val 2"], ["Val 3", "Val 4"]])
        self.assertIn("Col A", table)
        self.assertIn("Val 1", table)

    def test_agent_tree_visualizer(self):
        """Verify hierarchical stage and worker tree strings."""
        header = AgentTreeVisualizer.render_stage_header(1, 2, is_parallel=True, worker_count=2)
        self.assertIn("Stage 1/2", header)
        self.assertIn("PARALLEL", header)

        worker = AgentTreeVisualizer.render_worker_line(1, is_last=False, role="ResearchAgent", label="Web Search", goal="Search inference engines", status="RUNNING")
        self.assertIn("Worker 1", worker)
        self.assertIn("ResearchAgent", worker)
        self.assertIn("Search inference engines", worker)

    def test_skill_promotion_lifecycle(self):
        """Verify promoting a workflow creates a hashed, approved SKILL.md."""
        ledger_file = os.path.join(self.temp_dir, "trusted_plugins.json")
        mgr = SkillManager(
            search_paths=[os.path.join(self.temp_dir, ".nava", "skills")],
            ledger_path=ledger_file
        )
        
        orig_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            skill = mgr.promote_workflow_to_skill(
                skill_name="pdf_report_generator",
                description="Generates executive PDF summary reports.",
                instructions="Use ReportLab to format two-column executive briefs.",
                auto_approve=True
            )
            
            self.assertIsNotNone(skill)
            self.assertEqual(skill.name, "pdf_report_generator")
            self.assertEqual(skill.trust_state, "TRUSTED")
            self.assertTrue(os.path.exists(skill.filepath))
        finally:
            os.chdir(orig_cwd)

    def test_cowork_tui_slash_commands_dispatch(self):
        """Verify all slash commands execute without crashing."""
        mock_orch = MagicMock()
        mock_orch.workspace.project_name = "TestProject"
        mock_orch.workspace.list_projects.return_value = ["TestProject", "OtherProject"]
        mock_orch.workspace.read_memory.return_value = "# Project Memory"
        mock_orch.task_manager.list_tasks.return_value = [{"task_id": "tsk_1", "status": "COMPLETED", "goal": "Sample Goal"}]
        mock_orch.skill_manager.get_all_skills.return_value = {}
        mock_orch.skill_manager.get_trusted_skills.return_value = []
        
        mock_persona = MagicMock()
        mock_persona.name = "Test User"
        mock_persona.role = "Architect"
        mock_persona.preferred_communication_style = "concise"
        mock_persona.working_hours = "09:00 - 18:00"
        mock_persona.timezone = "UTC"
        mock_persona.security_constraints = ["No unapproved transfers"]
        mock_persona.authorized_tool_preferences = ["file.read"]
        mock_orch.ai_twin.get_persona.return_value = mock_persona
        mock_orch.budget_engine.budgets = {}
        
        tui = CoworkTUI(orchestrator=mock_orch)
        
        # Test banner
        tui.print_banner()
        
        # Test /help
        tui.dispatch_command("/help")
        
        # Test /twin
        tui.dispatch_command("/twin")
        
        # Test /budget
        tui.dispatch_command("/budget")
        
        # Test /projects
        tui.dispatch_command("/projects")
        
        # Test /tasks
        tui.dispatch_command("/tasks")
        
        # Test skills
        tui.dispatch_command("skills")
        
        # Test /mcp
        tui.dispatch_command("/mcp")
        
        # Test project
        tui.dispatch_command("project")
        
        # Test /kill
        tui.dispatch_command("/kill")
        mock_orch.emergency_stop.assert_called_once()

if __name__ == "__main__":
    unittest.main()
