import unittest
import os
import shutil
import tempfile
from nava.tools.registry import ToolRegistry
from nava.tools.tool_manifest import get_default_tools
from nava.tools.executor import LocalToolExecutor
from nava.core.schemas import ToolRequest

class TestCoreCodebaseIsolation(unittest.TestCase):
    def setUp(self):
        self.registry = ToolRegistry()
        for tool_def in get_default_tools():
            self.registry.register_tool(tool_def)
        self.executor = LocalToolExecutor(registry=self.registry)
        self.executor.set_active_project("TestApp")

    def test_file_read_blocks_internal_system_files(self):
        # 1. Attempting to read internal framework file -> BLOCKED
        req = ToolRequest(
            request_id="req-iso-1",
            agent_id="agt-1",
            tool_name="file.read",
            arguments={"filename": "src/nava/core/boot.py"},
            requested_scope="filesystem.read"
        )
        res = self.executor.execute(req)
        self.assertIn("error", res)
        self.assertIn("Access denied", res["error"])

        # 2. Attempting to read root nava.yaml -> BLOCKED
        req_yaml = ToolRequest(
            request_id="req-iso-2",
            agent_id="agt-1",
            tool_name="file.read",
            arguments={"filename": "nava.yaml"},
            requested_scope="filesystem.read"
        )
        res_yaml = self.executor.execute(req_yaml)
        self.assertIn("error", res_yaml)
        self.assertIn("Access denied", res_yaml["error"])

    def test_file_write_blocks_internal_system_files(self):
        # Attempting to mutate internal framework code -> BLOCKED
        req = ToolRequest(
            request_id="req-iso-3",
            agent_id="agt-1",
            tool_name="file.write",
            arguments={"filename": "src/nava/hacked.py", "content": "malicious code"},
            requested_scope="filesystem.write"
        )
        res = self.executor.execute(req)
        self.assertIn("error", res)
        self.assertIn("Access denied", res["error"])

    def test_code_search_scoped_to_projects_and_tasks(self):
        # Searching code does not crash or expose root system files
        req = ToolRequest(
            request_id="req-iso-4",
            agent_id="agt-1",
            tool_name="code.search",
            arguments={"query": "LocalToolExecutor"},
            requested_scope="ast.read"
        )
        res = self.executor.execute(req)
        # Should not find internal classes in projects/ workspace
        self.assertIn("results", res)
        self.assertNotIn("src/nava/tools/executor.py", res["results"])

if __name__ == "__main__":
    unittest.main()
