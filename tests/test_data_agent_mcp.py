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

class TestDataAgentMCP(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orig_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        self.executor = LocalToolExecutor()
        self.executor.set_active_task("tsk_test_data")
        
        self.registry = ToolRegistry()
        for t_name, scope in [
            ("sqlite.read_query", "database.read"),
            ("sqlite.write_query", "database.write"),
            ("sqlite.list_tables", "database.read"),
            ("sqlite.describe_tables", "database.read"),
            ("data.sql_query_csv", "data.analyze"),
            ("data.profile_dataset", "data.analyze"),
            ("data.aggregate", "data.analyze"),
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
        
        # Create a sample CSV file for tabular analytics
        self.sample_csv = os.path.join(self.temp_dir, "sales_sample.csv")
        with open(self.sample_csv, "w", encoding="utf-8") as f:
            f.write("region,sales,units,rep\n")
            f.write("North,15000,120,Alice\n")
            f.write("South,22000,180,Bob\n")
            f.write("East,18000,140,Charlie\n")
            f.write("West,31000,250,Diana\n")
            f.write("North,19000,160,Alice\n")

    def tearDown(self):
        os.chdir(self.orig_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sqlite_write_and_read_query(self):
        db_path = "test_analytics.db"
        
        # 1. Create table
        req_create = ToolRequest(
            request_id="req-db-1",
            agent_id="agt-data",
            tool_name="sqlite.write_query",
            arguments={
                "db_path": db_path,
                "query": "CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, tier TEXT, revenue REAL);"
            },
            requested_scope="database.write"
        )
        res_create = self.executor.execute(req_create)
        self.assertTrue(res_create.get("success", False))
        
        # 2. Insert rows
        req_insert = ToolRequest(
            request_id="req-db-2",
            agent_id="agt-data",
            tool_name="sqlite.write_query",
            arguments={
                "db_path": db_path,
                "query": "INSERT INTO customers (name, tier, revenue) VALUES ('Acme Corp', 'Enterprise', 50000.0), ('TechStart', 'SMB', 12000.0);"
            },
            requested_scope="database.write"
        )
        res_insert = self.executor.execute(req_insert)
        self.assertTrue(res_insert.get("success", False))
        self.assertEqual(res_insert.get("rows_affected"), 2)
        
        # 3. Read query (SELECT)
        req_select = ToolRequest(
            request_id="req-db-3",
            agent_id="agt-data",
            tool_name="sqlite.read_query",
            arguments={
                "db_path": db_path,
                "query": "SELECT * FROM customers WHERE revenue > 20000;"
            },
            requested_scope="database.read"
        )
        res_select = self.executor.execute(req_select)
        self.assertTrue(res_select.get("success", False))
        self.assertEqual(res_select.get("row_count"), 1)
        self.assertEqual(res_select["rows"][0]["name"], "Acme Corp")

    def test_sqlite_list_and_describe_tables(self):
        db_path = "test_schema.db"
        self.executor.execute(ToolRequest(
            request_id="req-s1", agent_id="agt-data", tool_name="sqlite.write_query",
            arguments={"db_path": db_path, "query": "CREATE TABLE products (sku TEXT PRIMARY KEY, price REAL, stock INT);"},
            requested_scope="database.write"
        ))
        
        # List tables
        res_list = self.executor.execute(ToolRequest(
            request_id="req-s2", agent_id="agt-data", tool_name="sqlite.list_tables",
            arguments={"db_path": db_path}, requested_scope="database.read"
        ))
        self.assertTrue(res_list.get("success", False))
        self.assertEqual(res_list.get("total_tables"), 1)
        self.assertEqual(res_list["tables"][0]["name"], "products")
        
        # Describe tables
        res_desc = self.executor.execute(ToolRequest(
            request_id="req-s3", agent_id="agt-data", tool_name="sqlite.describe_tables",
            arguments={"db_path": db_path, "table_name": "products"}, requested_scope="database.read"
        ))
        self.assertTrue(res_desc.get("success", False))
        self.assertIn("products", res_desc.get("schemas", {}))
        columns = res_desc["schemas"]["products"]["columns"]
        col_names = [c["name"] for c in columns]
        self.assertIn("sku", col_names)
        self.assertIn("price", col_names)

    def test_data_sql_query_csv(self):
        # Run SQL query directly over the CSV dataset
        req = ToolRequest(
            request_id="req-csv-1",
            agent_id="agt-data",
            tool_name="data.sql_query_csv",
            arguments={
                "csv_path": self.sample_csv,
                "query": "SELECT region, SUM(CAST(sales AS INT)) AS total_sales FROM dataset GROUP BY region ORDER BY total_sales DESC;"
            },
            requested_scope="data.analyze"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        self.assertEqual(res.get("row_count"), 4)
        # North region has 15000 + 19000 = 34000 (highest)
        self.assertEqual(res["rows"][0]["region"], "North")
        self.assertEqual(int(res["rows"][0]["total_sales"]), 34000)

    def test_data_profile_dataset(self):
        req = ToolRequest(
            request_id="req-prof-1",
            agent_id="agt-data",
            tool_name="data.profile_dataset",
            arguments={"csv_path": self.sample_csv},
            requested_scope="data.analyze"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        self.assertEqual(res.get("total_rows"), 5)
        self.assertEqual(res.get("total_columns"), 4)
        self.assertIn("sales", res.get("profiles", {}))
        self.assertEqual(res["profiles"]["sales"]["inferred_type"], "FLOAT/INT")

    def test_data_aggregate(self):
        req = ToolRequest(
            request_id="req-agg-1",
            agent_id="agt-data",
            tool_name="data.aggregate",
            arguments={
                "csv_path": self.sample_csv,
                "group_by": "region",
                "agg_column": "units",
                "agg_func": "SUM"
            },
            requested_scope="data.analyze"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        self.assertGreaterEqual(len(res.get("rows", [])), 1)

    def test_data_correlation_matrix(self):
        req = ToolRequest(
            request_id="req-corr-1",
            agent_id="agt-data",
            tool_name="data.correlation_matrix",
            arguments={"csv_path": self.sample_csv},
            requested_scope="data.analyze"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        self.assertIn("sales", res.get("correlation_matrix", {}))
        self.assertIn("units", res.get("correlation_matrix", {}))
        # Correlation with self is 1.0
        self.assertEqual(res["correlation_matrix"]["sales"]["sales"], 1.0)
        # Sales and units are positively correlated in sample data (> 0.9)
        self.assertGreater(res["correlation_matrix"]["sales"]["units"], 0.9)

    def test_data_detect_anomalies(self):
        # Add an outlier row to sample CSV
        with open(self.sample_csv, "a", encoding="utf-8") as f:
            f.write("OutlierRegion,999000,5000,SpamBot\n")
            
        req = ToolRequest(
            request_id="req-anom-1",
            agent_id="agt-data",
            tool_name="data.detect_anomalies",
            arguments={"csv_path": self.sample_csv, "column": "sales", "threshold": 1.5},
            requested_scope="data.analyze"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        self.assertGreaterEqual(res.get("anomalies_found", 0), 1)
        self.assertEqual(res["anomalies"][0]["value"], 999000.0)

    def test_data_pivot_table(self):
        req = ToolRequest(
            request_id="req-piv-1",
            agent_id="agt-data",
            tool_name="data.pivot_table",
            arguments={
                "csv_path": self.sample_csv,
                "index_col": "rep",
                "pivot_col": "region",
                "value_col": "sales",
                "agg_func": "SUM"
            },
            requested_scope="data.analyze"
        )
        res = self.executor.execute(req)
        self.assertTrue(res.get("success", False))
        self.assertIn("rep", res.get("columns", []))
        self.assertIn("North", res.get("columns", []))
        # Alice is in North region: 15000 + 19000 = 34000
        alice_row = next((r for r in res.get("rows", []) if r.get("rep") == "Alice"), None)
        self.assertIsNotNone(alice_row)
        self.assertEqual(alice_row.get("North"), 34000.0)

    def test_role_restriction_blocks_non_data_agents(self):
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
        
        # 1. Spawn DataAgent with sqlite.read_query & data.sql_query_csv -> MUST SUCCEED
        spec_data = AgentSpec(
            request_id="spec-data-1",
            requested_role="DataAgent",
            goal="Analyze database records",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["data.analyze", "database.read", "sqlite.*", "data.*"],
            requested_tools=["sqlite.read_query", "data.sql_query_csv"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-d1"
        )
        agent_data = self.factory.spawn_agent(spec_data, parent_state)
        self.assertIn("sqlite.read_query", agent_data.tool_scope)
        self.assertIn("data.sql_query_csv", agent_data.tool_scope)
        
        # 2. Attempt to spawn ResearchAgent or CodingAgent with sqlite.read_query -> MUST BE STRIPPED
        spec_research = AgentSpec(
            request_id="spec-res-2",
            requested_role="ResearchAgent",
            goal="Research documents",
            parent_agent_id="agt-root",
            ttl=timedelta(minutes=5),
            max_steps=10,
            max_tokens=10000,
            requested_permission_scope=["research.read", "database.read"],
            requested_tools=["sqlite.read_query", "data.sql_query_csv", "file.write"],
            max_children=2,
            priority=Priority.NORMAL,
            dedup_hash="hash-r2"
        )
        agent_research = self.factory.spawn_agent(spec_research, parent_state)
        self.assertNotIn("sqlite.read_query", agent_research.tool_scope)
        self.assertNotIn("data.sql_query_csv", agent_research.tool_scope)

if __name__ == "__main__":
    unittest.main()
