import os
import unittest
import tempfile
import shutil
from nava.tools.executor import LocalToolExecutor
from nava.tools.registry import ToolRegistry, ToolDefinition
from nava.core.schemas import ToolRequest, RiskTier

class TestCodingAgentSuperpowers(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        self.executor = LocalToolExecutor()
        self.executor.set_active_project("TestProject")
        
        # Create a sample Python module inside projects/TestProject/src/sample.py
        self.sample_code = '''"""Sample Math Module"""
import math

class Calculator:
    """Standard Calculator Class"""
    def __init__(self, precision=2):
        self.precision = precision

    def add(self, a: float, b: float) -> float:
        """Add two numbers"""
        return round(a + b, self.precision)

    def divide(self, a: float, b: float) -> float:
        """Divide two numbers"""
        if b == 0:
            raise ValueError("Division by zero")
        return round(a / b, self.precision)

def compute_square_root(n: float) -> float:
    """Compute square root of a number"""
    return math.sqrt(n)
'''
        self.executor.execute(ToolRequest(
            request_id="req-setup",
            agent_id="agt-test",
            tool_name="file.write",
            arguments={"filename": "src/sample.py", "content": self.sample_code},
            requested_scope="filesystem.write"
        ))

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_context7_get_symbol_graph(self):
        req = ToolRequest(
            request_id="req-1",
            agent_id="agt-test",
            tool_name="context7.get_symbol_graph",
            arguments={"filename": "src/sample.py"},
            requested_scope="filesystem.read"
        )
        res = self.executor.execute(req)
        self.assertIn("symbol_graph", res)
        self.assertGreaterEqual(res["total_symbols_extracted"], 3)
        
        # Verify Calculator class and methods were extracted
        graph = res["symbol_graph"][0]
        class_names = [c["name"] for c in graph["classes"]]
        self.assertIn("Calculator", class_names)
        self.assertIn("add", graph["classes"][0]["methods"])
        self.assertIn("divide", graph["classes"][0]["methods"])

    def test_context7_slice_context(self):
        req = ToolRequest(
            request_id="req-2",
            agent_id="agt-test",
            tool_name="context7.slice_context",
            arguments={"filename": "src/sample.py", "symbol_name": "divide"},
            requested_scope="filesystem.read"
        )
        res = self.executor.execute(req)
        self.assertIn("snippet", res)
        self.assertIn("def divide", res["snippet"])
        self.assertIn("token_reduction", res)
        self.assertTrue(res["token_reduction"].endswith("%"))

    def test_superpowers_ast_search(self):
        req = ToolRequest(
            request_id="req-3",
            agent_id="agt-test",
            tool_name="superpowers.ast_search",
            arguments={"filename": "src/sample.py", "pattern": "Calculator"},
            requested_scope="filesystem.read"
        )
        res = self.executor.execute(req)
        self.assertIn("matches", res)
        self.assertGreaterEqual(res["total_found"], 1)
        self.assertEqual(res["matches"][0]["node_type"], "ClassDef")
        self.assertEqual(res["matches"][0]["name"], "Calculator")

    def test_superpowers_ast_replace(self):
        req = ToolRequest(
            request_id="req-4",
            agent_id="agt-test",
            tool_name="superpowers.ast_replace",
            arguments={
                "filename": "src/sample.py",
                "target_symbol": "return round(a + b, self.precision)",
                "replacement_code": "return float(a + b)"
            },
            requested_scope="filesystem.write"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success"))
        
        # Verify modified file
        read_res = self.executor.execute(ToolRequest(
            request_id="req-5",
            agent_id="agt-test",
            tool_name="file.read",
            arguments={"filename": "src/sample.py"},
            requested_scope="filesystem.read"
        ))
        self.assertIn("return float(a + b)", read_res["content"])

    def test_superpowers_compiler_autofix(self):
        # Create a file with a missing colon syntax error
        broken_code = """def broken_function(x, y)
    return x + y
"""
        self.executor.execute(ToolRequest(
            request_id="req-6",
            agent_id="agt-test",
            tool_name="file.write",
            arguments={"filename": "src/broken.py", "content": broken_code},
            requested_scope="filesystem.write"
        ))
        
        # Run compiler autofix
        req = ToolRequest(
            request_id="req-7",
            agent_id="agt-test",
            tool_name="superpowers.compiler_autofix",
            arguments={"filename": "src/broken.py"},
            requested_scope="filesystem.write"
        )
        res = self.executor.execute(req)
        self.assertEqual(res.get("status"), "AUTO_FIXED")
        self.assertIn("repaired", res)
        self.assertTrue(res["repaired"].endswith(":"))

if __name__ == "__main__":
    unittest.main()
