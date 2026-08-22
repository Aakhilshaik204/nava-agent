import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from nava.workspace.project_manager import ProjectWorkspace
from nava.workspace.indexer import ProjectIndexer

class TestProjectWorkspace(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_project_workspace_initialization(self):
        """Verify .nava/project_memory.md is generated with structured markdown sections."""
        ws = ProjectWorkspace(root_dir=self.temp_dir)
        content = ws.initialize_project_memory(project_goal="Test Suite Goal")
        
        self.assertTrue(os.path.exists(ws.memory_path))
        self.assertIn("# 📌 Project Workspace Memory", content)
        self.assertIn("## 🎯 1. Project Overview & Architecture", content)
        self.assertIn("## 📍 2. Current Execution State", content)
        self.assertIn("## 📝 3. Architectural Decisions & Constraints", content)
        self.assertIn("## ⏳ 4. Resume Queue", content)
        self.assertIn("Test Suite Goal", content)

    def test_project_indexer_ast_parsing(self):
        """Verify AST indexer parses Python classes, functions, docstrings and builds index."""
        # Create dummy python file
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

        # Test symbol searching
        results = indexer.search_symbols("checksum")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["name"], "calculate_checksum")

    def test_checkpoint_persistence_and_resume_context(self):
        """Verify checkpoint saving updates markdown and generates prompt context."""
        ws = ProjectWorkspace(root_dir=self.temp_dir)
        ws.initialize_project_memory()

        ws.save_checkpoint(
            task_id="task-99",
            objective="Refactoring JWT tokens",
            last_agent="CodingAgent",
            touched_files=["src/jwt.py", "tests/test_jwt.py"],
            next_steps=["Add token rotation", "Run test suite"],
            status="READY_TO_RESUME"
        )

        content = ws.read_memory()
        self.assertIn("Refactoring JWT tokens", content)
        self.assertIn("CodingAgent (task-99)", content)
        self.assertIn("src/jwt.py", content)
        self.assertIn("1. [ ] Add token rotation", content)
        self.assertIn("2. [ ] Run test suite", content)

        resume_ctx = ws.get_resume_context()
        self.assertIsNotNone(resume_ctx)
        self.assertIn("[PROJECT CONTINUITY CONTEXT]", resume_ctx)
        self.assertIn("Refactoring JWT tokens", resume_ctx)

    def test_append_architectural_decision(self):
        """Verify appending decisions maintains Section 3 format."""
        ws = ProjectWorkspace(root_dir=self.temp_dir)
        ws.initialize_project_memory()

        ws.append_decision("Using RS256 algorithm instead of HS256.")
        content = ws.read_memory()
        self.assertIn("Using RS256 algorithm instead of HS256.", content)

    def test_file_snapshot_and_rollback(self):
        """Verify file snapshots are created in .nava/checkpoints/ and can be restored."""
        ws = ProjectWorkspace(root_dir=self.temp_dir)
        test_file = os.path.join(self.temp_dir, "config.json")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('{"version": 1}')

        # Create snapshot
        snap_dir = ws.create_file_snapshot("snap-1", ["config.json"])
        self.assertTrue(os.path.exists(snap_dir))
        self.assertTrue(os.path.exists(os.path.join(snap_dir, "manifest.json")))

        # Modify file
        with open(test_file, "w", encoding="utf-8") as f:
            f.write('{"version": 2}')

        # Restore snapshot
        success = ws.restore_file_snapshot("snap-1")
        self.assertTrue(success)

        # Verify restoration
        with open(test_file, "r", encoding="utf-8") as f:
            restored = f.read()
        self.assertEqual(restored, '{"version": 1}')

    def test_welcome_back_message_formatting(self):
        """Verify get_welcome_back_message formats startup greeting correctly."""
        ws = ProjectWorkspace(root_dir=self.temp_dir)
        ws.initialize_project_memory()

        # Before any task
        msg_none = ws.get_welcome_back_message()
        self.assertIsNone(msg_none)

        # Save checkpoint
        ws.save_checkpoint(
            task_id="tsk-001",
            objective="Migrate SQLite schema",
            last_agent="DatabaseAgent",
            touched_files=["schema.sql"],
            next_steps=["Run migration script"]
        )

        msg = ws.get_welcome_back_message()
        self.assertIsNotNone(msg)
        self.assertIn("WORKSPACE CONTEXT CONTINUITY", msg)
        self.assertIn("Migrate SQLite schema", msg)
        self.assertIn("DatabaseAgent", msg)
        self.assertIn("Run migration script", msg)

        obj = ws.get_active_objective()
        self.assertEqual(obj, "Migrate SQLite schema")

if __name__ == "__main__":
    unittest.main()
