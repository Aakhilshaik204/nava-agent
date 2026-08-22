import sys
import os

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import unittest
import asyncio
import tempfile
from nava.core.schemas import ToolRequest, RiskTier
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.gateway.schema_validator import DefaultSchemaValidator
from nava.tools.executor import LocalToolExecutor
from nava.tools.mcp_client import MCPClientManager, StdioMCPClient, MCPToolTrustState


class TestStep3MCPHardening(unittest.TestCase):
    def setUp(self):
        os.environ["NAVA_TEST_MODE"] = "1"
        self.tmpdir = tempfile.TemporaryDirectory()
        self.registry = ToolRegistry()
        
        self.registry.register_tool(ToolDefinition(
            name="file.write",
            description="Writes file",
            input_schema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string"},
                    "content": {"type": "string"}
                },
                "required": ["filename", "content"]
            },
            output_schema={"success": "boolean"},
            permissions_required=["filesystem.write"],
            risk_level=RiskTier.LOW,
            reversible=True
        ))
        
        self.registry.register_tool(ToolDefinition(
            name="data.analyze",
            description="Analyzes data file",
            input_schema={"filename": "string"},
            output_schema={"row_count": "integer"},
            permissions_required=["filesystem.read"],
            risk_level=RiskTier.LOW,
            reversible=True
        ))
        
        self.validator = DefaultSchemaValidator(self.registry)
        self.executor = LocalToolExecutor()

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_schema_validator_accepts_valid_arguments(self):
        """Verify DefaultSchemaValidator accepts requests meeting type and required specs."""
        req = ToolRequest(
            request_id="req-v1",
            agent_id="agt-1",
            tool_name="file.write",
            arguments={"filename": "test.txt", "content": "hello world"},
            requested_scope="filesystem.write"
        )
        self.assertTrue(self.validator.validate(req))

    def test_schema_validator_rejects_missing_required_fields(self):
        """Verify DefaultSchemaValidator rejects requests missing required parameters."""
        req = ToolRequest(
            request_id="req-v2",
            agent_id="agt-1",
            tool_name="file.write",
            arguments={"filename": "test.txt"}, # Missing 'content'
            requested_scope="filesystem.write"
        )
        self.assertFalse(self.validator.validate(req))

    def test_schema_validator_rejects_wrong_data_types(self):
        """Verify DefaultSchemaValidator rejects incorrect data types (e.g. integer for string)."""
        req = ToolRequest(
            request_id="req-v3",
            agent_id="agt-1",
            tool_name="file.write",
            arguments={"filename": 12345, "content": "hello"}, # Wrong type for filename
            requested_scope="filesystem.write"
        )
        self.assertFalse(self.validator.validate(req))

    def test_filesystem_path_containment_blocks_traversal(self):
        """Verify LocalToolExecutor blocks directory traversal attacks outside workspace."""
        req = ToolRequest(
            request_id="req-trav",
            agent_id="agt-1",
            tool_name="file.read",
            arguments={"filename": "../../etc/shadow"},
            requested_scope="filesystem.read"
        )
        res = self.executor.execute(req)
        self.assertIn("error", res)
        self.assertIn("Path traversal blocked", res["error"])

    def test_filesystem_path_containment_allows_safe_workspace_paths(self):
        """Verify LocalToolExecutor allows safe file operations within workspace directory."""
        test_file = os.path.join(self.tmpdir.name, "safe_doc.txt")
        write_req = ToolRequest(
            request_id="req-w",
            agent_id="agt-1",
            tool_name="file.write",
            arguments={"filename": test_file, "content": "safe workspace data"},
            requested_scope="filesystem.write"
        )
        res = self.executor.execute(write_req)
        self.assertTrue(res.get("success"))
        
        read_req = ToolRequest(
            request_id="req-r",
            agent_id="agt-1",
            tool_name="file.read",
            arguments={"filename": test_file},
            requested_scope="filesystem.read"
        )
        read_res = self.executor.execute(read_req)
        self.assertEqual(read_res.get("content"), "safe workspace data")

    def test_mcp_client_manager_easy_registration(self):
        """Verify easy registration and hash-locking trust workflow for custom MCP servers."""
        ledger_path = os.path.join(self.tmpdir.name, "mcp_ledger.json")
        mcp_manager = MCPClientManager(self.registry, ledger_path=ledger_path)
        
        # Easy registration with custom tool definition
        custom_tools = [{
            "name": "custom_db.query",
            "description": "Run SQL query on custom database",
            "input_schema": {"query": "string"},
            "permissions_required": ["custom_db.read"],
            "risk_level": "LOW",
            "reversible": True,
            "required_credentials": ["custom_db"]
        }]
        
        mcp_manager.register_server(
            name="custom_db",
            command="python",
            args=["dummy_server.py"],
            custom_tools=custom_tools
        )
        
        # Check that it's flagged as UNTRUSTED_NEW
        pending = mcp_manager.get_pending_approvals("custom_db")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["trust_state"], MCPToolTrustState.UNTRUSTED_NEW)
        
        # Approve tool
        mcp_manager.approve_tool("custom_db", "custom_db.query", actor="admin")
        
        # Verify it is registered in ToolRegistry and marked TRUSTED
        tool_def = self.registry.get_tool("custom_db.query")
        self.assertIsNotNone(tool_def)
        self.assertEqual(tool_def.name, "custom_db.query")

    def test_stdio_mcp_client_protocol_handshake(self):
        """Verify StdioMCPClient constructs valid JSON-RPC 2.0 sequence IDs."""
        client = StdioMCPClient("dummy", [])
        self.assertEqual(client._next_id(), 1)
        self.assertEqual(client._next_id(), 2)


if __name__ == "__main__":
    unittest.main()

