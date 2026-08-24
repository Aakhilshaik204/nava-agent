import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from nava.workspace.project_manager import ProjectWorkspace, TaskManager
from nava.workspace.indexer import ProjectIndexer

class TestProjectWorkspace(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_project_workspace_initialization(self):
        """Verify project_memory.md is generated with structured markdown sections."""
        ws = ProjectWorkspace(root_dir=self.temp_dir, project_name="NavaTest")
        content = ws.initialize_project_memory(project_goal="Test Suite Goal")
        
        self.assertTrue(os.path.exists(ws.memory_path))
        self.assertIn("# 📌 Project Workspace Memory: NavaTest", content)
        self.assertIn("## 🎯 1. Project Overview & Architecture", content)
        self.assertIn("## 📝 2. Architectural Decisions & Constraints", content)
        self.assertIn("Test Suite Goal", content)

    def test_task_manager_isolation_and_memory(self):
        """Verify TaskManager creates isolated tasks with task_memory.md and task-scoped artifacts."""
        tm = TaskManager(root_dir=self.temp_dir)
        
        # 1. Create a task
        task_id = tm.create_task("Take a screenshot of screen", project_id="NavaTest")
        self.assertTrue(os.path.exists(tm.get_task_dir(task_id)))
        self.assertTrue(os.path.exists(tm.get_task_artifacts_dir(task_id)))
        
        # 2. Verify initial task_memory.md
        mem = tm.get_task_memory(task_id)
        self.assertIn("Take a screenshot of screen", mem)
        self.assertIn("Status**: RUNNING", mem)
        
        # 3. Record plan
        tm.record_plan(task_id, ["[Stage 1] ComputerAgent → Capture desktop screen"])
        mem = tm.get_task_memory(task_id)
        self.assertIn("ComputerAgent → Capture desktop screen", mem)
        
        # 4. Record action and artifact
        tm.record_action(task_id, "ComputerAgent", "desktop.screenshot", {"path": "screen.png"}, "SUCCESS")
        tm.record_artifact(task_id, os.path.join(tm.get_task_artifacts_dir(task_id), "screen.png"))
        
        mem = tm.get_task_memory(task_id)
        self.assertIn("desktop.screenshot", mem)
        self.assertIn("screen.png", mem)
        
        # 5. Complete task
        tm.complete_task(task_id, outcome_summary="Screenshot captured successfully.", is_success=True)
        mem = tm.get_task_memory(task_id)
        self.assertIn("Status**: COMPLETED", mem)
        self.assertIn("Screenshot captured successfully", mem)
        
        # 6. List tasks
        tasks = tm.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], task_id)
        self.assertEqual(tasks[0]["status"], "COMPLETED")

    def test_project_indexer_ast_parsing(self):
        """Verify AST indexer parses Python classes, functions, docstrings and builds index."""
        dummy_code = '''"""Module level docstring."""
class UserAuthService:
    """Manages user authentication."""
    def login(self, username: str):
        """Performs login operation."""
        return True

def calculate_checksum(data: str) -> str:
    """Computes SHA256 checksum."""
    return "hash123"
'''
        sample_file = os.path.join(self.temp_dir, "auth_service.py")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write(dummy_code)

        indexer = ProjectIndexer(self.temp_dir)
        index = indexer.build_index()

        self.assertEqual(index["total_files"], 1)
        self.assertIn("Python", index["tech_stack"])
        
        symbol_names = [s["name"] for s in index["symbols"]]
        self.assertIn("UserAuthService", symbol_names)
        self.assertIn("UserAuthService.login", symbol_names)
        self.assertIn("calculate_checksum", symbol_names)

        results = indexer.search_symbols("checksum")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["name"], "calculate_checksum")

    def test_append_architectural_decision(self):
        """Verify appending decisions maintains Section 2 format in project_memory.md."""
        ws = ProjectWorkspace(root_dir=self.temp_dir, project_name="NavaTest")
        ws.initialize_project_memory()

        ws.append_decision("Using RS256 algorithm instead of HS256.")
        content = ws.read_memory()
        self.assertIn("Using RS256 algorithm instead of HS256.", content)

    def test_welcome_back_message_formatting(self):
        """Verify get_welcome_back_message formats startup greeting correctly from TaskManager."""
        ws = ProjectWorkspace(root_dir=self.temp_dir, project_name="NavaTest")
        ws.initialize_project_memory()

        # Before any task
        msg_none = ws.get_welcome_back_message()
        self.assertIsNone(msg_none)

        # Create task
        task_id = ws.task_manager.create_task("Migrate SQLite schema")
        ws.task_manager.complete_task(task_id, "Migration complete.", is_success=True)

        msg = ws.get_welcome_back_message()
        self.assertIsNotNone(msg)
        self.assertIn("WORKSPACE CONTEXT CONTINUITY", msg)
        self.assertIn("Migrate SQLite schema", msg)
        self.assertIn("COMPLETED", msg)

    def test_executor_project_codebase_isolation(self):
        """Verify LocalToolExecutor routes codebase files strictly inside projects/<active_project>/."""
        from nava.tools.executor import LocalToolExecutor
        
        orig_cwd = os.getcwd()
        try:
            os.chdir(self.temp_dir)
            executor = LocalToolExecutor()
            executor.set_active_project("EcommerceApp")
            executor.set_active_task("tsk_demo_123")
            
            # Write a codebase file
            res = executor._file_write({"filename": "src/api/routes.py", "content": "print('hello routes')"})
            self.assertTrue(res["success"])
            
            expected_path = os.path.join(self.temp_dir, "projects", "EcommerceApp", "src", "api", "routes.py")
            self.assertTrue(os.path.exists(expected_path))
            
            # Read the codebase file
            read_res = executor._file_read({"filename": "src/api/routes.py"})
            self.assertEqual(read_res["content"], "print('hello routes')")
            
            # Write a standalone task deliverable (PDF/Docx/scratch)
            res_pdf = executor._file_write({"filename": "architecture_diagram.pdf", "content": "%PDF-1.4..."})
            expected_pdf_path = os.path.join(self.temp_dir, "tasks", "tsk_demo_123", "artifacts", "architecture_diagram.pdf")
            self.assertTrue(os.path.exists(expected_pdf_path))
        finally:
            os.chdir(orig_cwd)

if __name__ == "__main__":
    unittest.main()
