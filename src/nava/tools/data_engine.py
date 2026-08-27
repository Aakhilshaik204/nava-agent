import os
import csv
import json
import sqlite3
from typing import Dict, Any, List, Optional, Callable

class DataEngine:
    """
    Dedicated Modular Data & Database Engine for NAVA DataAgent.
    Provides official SQLite database operations and high-performance in-memory tabular SQL analytics.
    """
    def __init__(
        self,
        path_resolver: Optional[Callable[[str], str]] = None,
        artifact_resolver: Optional[Callable[[str], str]] = None,
        sanitizer: Optional[Callable[[str], str]] = None
    ):
        self.path_resolver = path_resolver
        self.artifact_resolver = artifact_resolver
        self.sanitizer = sanitizer

    def _resolve_target(self, target: str) -> str:
        """Resolves target database/csv path checking task artifacts, project workspace, and relative paths."""
        if not target:
            raise ValueError("Target path cannot be empty")
            
        candidates = []
        if self.artifact_resolver:
            candidates.append(self.artifact_resolver(target))
        if self.path_resolver:
            candidates.append(self.path_resolver(target))
        if self.sanitizer:
            candidates.append(self.sanitizer(target))
        candidates.append(os.path.abspath(target))
        
        # Pick first candidate that exists physically on disk
        for c in candidates:
            if os.path.exists(c):
                return c
                
        # If none exist yet (e.g. creating a new db/file), use artifact_resolver or sanitizer
        if self.artifact_resolver and ("/" not in target.replace("\\", "/") or target.startswith(("artifacts/", "tasks/"))):
            return self.artifact_resolver(target)
        if self.path_resolver and "/" in target.replace("\\", "/"):
            return self.path_resolver(target)
        if self.sanitizer:
            return self.sanitizer(target)
            
        return os.path.abspath(target)

    # =========================================================================
    # 1. SQLite Database MCP Operations (sqlite.*)
    # =========================================================================
    def read_query(self, db_path: str, query: str, max_rows: int = 100) -> Dict[str, Any]:
        """Executes a SELECT query against a SQLite database with row truncation and schema metadata."""
        if not query:
            return {"error": "query is required"}
            
        resolved_db = self._resolve_target(db_path)
        if not os.path.exists(resolved_db):
            return {"error": f"Database file '{db_path}' does not exist."}
            
        # Enforce read-only safety for read_query
        normalized_q = query.strip().upper()
        if not normalized_q.startswith(("SELECT", "PRAGMA", "EXPLAIN", "WITH")):
            return {"error": "read_query only supports SELECT, PRAGMA, EXPLAIN, or WITH queries. Use write_query for mutations."}
            
        try:
            conn = sqlite3.connect(resolved_db)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            raw_rows = cursor.fetchmany(max_rows)
            rows = [dict(row) for row in raw_rows]
            
            conn.close()
            return {
                "success": True,
                "db_path": os.path.relpath(resolved_db, os.getcwd()),
                "columns": columns,
                "row_count": len(rows),
                "rows": rows,
                "truncated": len(rows) == max_rows
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def write_query(self, db_path: str, query: str) -> Dict[str, Any]:
        """Executes CREATE, INSERT, UPDATE, DELETE queries on a SQLite database within a transaction."""
        if not query:
            return {"error": "query is required"}
            
        resolved_db = self._resolve_target(db_path)
        os.makedirs(os.path.dirname(resolved_db), exist_ok=True)
        
        try:
            conn = sqlite3.connect(resolved_db)
            cursor = conn.cursor()
            cursor.execute(query)
            conn.commit()
            
            rows_affected = cursor.rowcount
            last_id = cursor.lastrowid
            conn.close()
            
            return {
                "success": True,
                "db_path": os.path.relpath(resolved_db, os.getcwd()),
                "rows_affected": rows_affected,
                "last_insert_id": last_id,
                "message": "Query executed and committed successfully."
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_tables(self, db_path: str) -> Dict[str, Any]:
        """Lists all tables and views in a SQLite database with row count metrics."""
        resolved_db = self._resolve_target(db_path)
        if not os.path.exists(resolved_db):
            return {"error": f"Database file '{db_path}' does not exist."}
            
        try:
            conn = sqlite3.connect(resolved_db)
            cursor = conn.cursor()
            cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%';")
            entries = cursor.fetchall()
            
            tables = []
            for name, entity_type in entries:
                try:
                    count_cur = conn.cursor()
                    count_cur.execute(f"SELECT COUNT(*) FROM \"{name}\"")
                    count = count_cur.fetchone()[0]
                except Exception:
                    count = "unknown"
                    
                tables.append({
                    "name": name,
                    "type": entity_type,
                    "row_count": count
                })
                
            conn.close()
            return {
                "success": True,
                "db_path": os.path.relpath(resolved_db, os.getcwd()),
                "total_tables": len(tables),
                "tables": tables
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def describe_tables(self, db_path: str, table_name: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves detailed column definitions, data types, primary keys, and schema definitions."""
        resolved_db = self._resolve_target(db_path)
        if not os.path.exists(resolved_db):
            return {"error": f"Database file '{db_path}' does not exist."}
            
        try:
            conn = sqlite3.connect(resolved_db)
            cursor = conn.cursor()
            
            if table_name:
                target_tables = [table_name]
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
                target_tables = [row[0] for row in cursor.fetchall()]
                
            schemas = {}
            for tbl in target_tables:
                cursor.execute(f"PRAGMA table_info(\"{tbl}\");")
                columns = []
                for col in cursor.fetchall():
                    columns.append({
                        "cid": col[0],
                        "name": col[1],
                        "type": col[2],
                        "not_null": bool(col[3]),
                        "default_value": col[4],
                        "is_primary_key": bool(col[5])
                    })
                    
                cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=\"{tbl}\";")
                create_sql = cursor.fetchone()
                
                schemas[tbl] = {
                    "columns": columns,
                    "create_statement": create_sql[0] if create_sql else ""
                }
                
            conn.close()
            return {
                "success": True,
                "db_path": os.path.relpath(resolved_db, os.getcwd()),
                "schemas": schemas
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # 2. In-Memory Tabular SQL Analytics (data.*)
    # =========================================================================
    def sql_query_csv(self, csv_path: str, query: str, table_name: str = "dataset", max_rows: int = 100) -> Dict[str, Any]:
        """
        Loads a CSV into an in-memory SQLite table and executes full SQL queries on it on-the-fly.
        Enables SQL querying on datasets without requiring a pre-existing database.
        """
        if not query:
            return {"error": "query is required"}
            
        resolved_csv = self._resolve_target(csv_path)
        if not os.path.exists(resolved_csv):
            return {"error": f"CSV file '{csv_path}' does not exist."}
            
        try:
            with open(resolved_csv, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers:
                    return {"error": f"CSV file '{csv_path}' is empty."}
                    
                # Sanitize column names for SQLite
                clean_headers = [h.strip().replace(" ", "_").replace("-", "_").replace(".", "_") for h in headers]
                rows = list(reader)
                
            # Create in-memory SQLite table
            mem_conn = sqlite3.connect(":memory:")
            mem_conn.row_factory = sqlite3.Row
            mem_cur = mem_conn.cursor()
            
            cols_def = ", ".join([f'"{h}" TEXT' for h in clean_headers])
            mem_cur.execute(f'CREATE TABLE "{table_name}" ({cols_def});')
            
            placeholders = ", ".join(["?"] * len(clean_headers))
            insert_sql = f'INSERT INTO "{table_name}" VALUES ({placeholders})'
            mem_cur.executemany(insert_sql, rows)
            mem_conn.commit()
            
            # Execute user query
            mem_cur.execute(query)
            result_cols = [desc[0] for desc in mem_cur.description] if mem_cur.description else []
            fetched_rows = [dict(r) for r in mem_cur.fetchmany(max_rows)]
            
            mem_conn.close()
            return {
                "success": True,
                "source_csv": os.path.relpath(resolved_csv, os.getcwd()),
                "table_name": table_name,
                "columns": result_cols,
                "row_count": len(fetched_rows),
                "rows": fetched_rows,
                "truncated": len(fetched_rows) == max_rows
            }
        except Exception as e:
            return {"success": False, "error": f"SQL CSV query failed: {str(e)}"}

    def profile_dataset(self, csv_path: str) -> Dict[str, Any]:
        """
        Profiles a tabular CSV dataset: row count, column data types, missing value percentages,
        unique counts, and numeric statistics (min, max, mean).
        """
        resolved_csv = self._resolve_target(csv_path)
        if not os.path.exists(resolved_csv):
            return {"error": f"CSV file '{csv_path}' does not exist."}
            
        try:
            with open(resolved_csv, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers:
                    return {"error": "CSV is empty"}
                rows = list(reader)
                
            total_rows = len(rows)
            column_profiles = {}
            
            for col_idx, col_name in enumerate(headers):
                values = [r[col_idx] for r in rows if len(r) > col_idx]
                non_empty = [v.strip() for v in values if v.strip() != ""]
                null_count = total_rows - len(non_empty)
                null_pct = round((null_count / total_rows * 100), 2) if total_rows > 0 else 0
                unique_vals = set(non_empty)
                
                # Check if numeric
                numeric_vals = []
                for v in non_empty:
                    try:
                        numeric_vals.append(float(v.replace(",", "").replace("$", "")))
                    except ValueError:
                        pass
                        
                is_numeric = len(numeric_vals) == len(non_empty) and len(non_empty) > 0
                
                prof = {
                    "total_values": len(values),
                    "null_count": null_count,
                    "null_percentage": f"{null_pct}%",
                    "unique_count": len(unique_vals),
                    "inferred_type": "FLOAT/INT" if is_numeric else "STRING"
                }
                
                if is_numeric and numeric_vals:
                    prof["stats"] = {
                        "min": min(numeric_vals),
                        "max": max(numeric_vals),
                        "mean": round(sum(numeric_vals) / len(numeric_vals), 2)
                    }
                else:
                    sample = list(unique_vals)[:5]
                    prof["sample_values"] = sample
                    
                column_profiles[col_name] = prof
                
            return {
                "success": True,
                "source_file": os.path.relpath(resolved_csv, os.getcwd()),
                "total_rows": total_rows,
                "total_columns": len(headers),
                "columns": headers,
                "profiles": column_profiles
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to profile dataset: {str(e)}"}

    def aggregate_data(self, csv_path: str, group_by: str, agg_column: str, agg_func: str = "SUM") -> Dict[str, Any]:
        """Performs structured GROUP BY aggregations on tabular data (SUM, AVG, MIN, MAX, COUNT)."""
        valid_funcs = ["SUM", "AVG", "MIN", "MAX", "COUNT"]
        func = agg_func.upper()
        if func not in valid_funcs:
            return {"error": f"Invalid agg_func '{agg_func}'. Must be one of {valid_funcs}"}
            
        query = f'SELECT "{group_by}", {func}("{agg_column}") AS "{func.lower()}_{agg_column}" FROM dataset GROUP BY "{group_by}" ORDER BY "{func.lower()}_{agg_column}" DESC;'
        return self.sql_query_csv(csv_path, query, table_name="dataset")

    def correlation_matrix(self, csv_path: str) -> Dict[str, Any]:
        """Computes pairwise Pearson correlation coefficients across all numeric columns in a dataset."""
        resolved_csv = self._resolve_target(csv_path)
        if not os.path.exists(resolved_csv):
            return {"error": f"CSV file '{csv_path}' does not exist."}
            
        try:
            with open(resolved_csv, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers:
                    return {"error": "CSV is empty"}
                rows = list(reader)
                
            # Extract numeric columns
            numeric_cols = {}
            for col_idx, col_name in enumerate(headers):
                vals = []
                for r in rows:
                    if len(r) > col_idx and r[col_idx].strip():
                        try:
                            vals.append(float(r[col_idx].replace(",", "").replace("$", "")))
                        except ValueError:
                            pass
                if len(vals) == len(rows) and len(vals) > 1:
                    numeric_cols[col_name] = vals
                    
            col_names = list(numeric_cols.keys())
            if len(col_names) < 2:
                return {"error": "At least 2 numeric columns are required to compute a correlation matrix.", "numeric_columns_found": col_names}
                
            matrix = {}
            for col1 in col_names:
                matrix[col1] = {}
                v1 = numeric_cols[col1]
                mean1 = sum(v1) / len(v1)
                std1 = (sum((x - mean1) ** 2 for x in v1) / len(v1)) ** 0.5
                
                for col2 in col_names:
                    if col1 == col2:
                        matrix[col1][col2] = 1.0
                        continue
                    v2 = numeric_cols[col2]
                    mean2 = sum(v2) / len(v2)
                    std2 = (sum((y - mean2) ** 2 for y in v2) / len(v2)) ** 0.5
                    
                    if std1 == 0 or std2 == 0:
                        matrix[col1][col2] = 0.0
                    else:
                        covariance = sum((x - mean1) * (y - mean2) for x, y in zip(v1, v2)) / len(v1)
                        matrix[col1][col2] = round(covariance / (std1 * std2), 4)
                        
            return {
                "success": True,
                "source_file": os.path.relpath(resolved_csv, os.getcwd()),
                "numeric_columns": col_names,
                "correlation_matrix": matrix
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to compute correlation matrix: {str(e)}"}

    def detect_anomalies(self, csv_path: str, column: str, threshold: float = 2.5) -> Dict[str, Any]:
        """Identifies statistical anomalies and outliers in a numeric column using Z-Score analysis."""
        resolved_csv = self._resolve_target(csv_path)
        if not os.path.exists(resolved_csv):
            return {"error": f"CSV file '{csv_path}' does not exist."}
            
        try:
            with open(resolved_csv, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers or column not in headers:
                    return {"error": f"Column '{column}' not found in CSV headers: {headers}"}
                col_idx = headers.index(column)
                rows = list(reader)
                
            entries = []
            for r_idx, r in enumerate(rows, 2): # 1-indexed header is line 1
                if len(r) > col_idx and r[col_idx].strip():
                    try:
                        val = float(r[col_idx].replace(",", "").replace("$", ""))
                        entries.append({"line_number": r_idx, "value": val, "row": r})
                    except ValueError:
                        pass
                        
            if len(entries) < 3:
                return {"error": f"Not enough numeric data in column '{column}' for outlier detection."}
                
            vals = [e["value"] for e in entries]
            mean_val = sum(vals) / len(vals)
            std_dev = (sum((x - mean_val) ** 2 for x in vals) / len(vals)) ** 0.5
            
            if std_dev == 0:
                return {"success": True, "anomalies_found": 0, "anomalies": [], "message": "Zero variance across all entries."}
                
            anomalies = []
            for e in entries:
                z_score = abs(e["value"] - mean_val) / std_dev
                if z_score >= threshold:
                    anomalies.append({
                        "line_number": e["line_number"],
                        "value": e["value"],
                        "z_score": round(z_score, 2),
                        "row_data": dict(zip(headers, e["row"]))
                    })
                    
            return {
                "success": True,
                "column": column,
                "mean": round(mean_val, 2),
                "std_dev": round(std_dev, 2),
                "threshold_z_score": threshold,
                "anomalies_found": len(anomalies),
                "anomalies": anomalies
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to detect anomalies: {str(e)}"}

    def pivot_table(self, csv_path: str, index_col: str, pivot_col: str, value_col: str, agg_func: str = "SUM") -> Dict[str, Any]:
        """Creates a cross-tabulated 2D pivot table from tabular data."""
        resolved_csv = self._resolve_target(csv_path)
        if not os.path.exists(resolved_csv):
            return {"error": f"CSV file '{csv_path}' does not exist."}
            
        try:
            with open(resolved_csv, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                if not headers:
                    return {"error": "CSV is empty"}
                for c in [index_col, pivot_col, value_col]:
                    if c not in headers:
                        return {"error": f"Required column '{c}' not found in headers: {headers}"}
                        
                idx_i = headers.index(index_col)
                piv_i = headers.index(pivot_col)
                val_i = headers.index(value_col)
                rows = list(reader)
                
            pivot_data = {}
            all_pivot_keys = set()
            for r in rows:
                if len(r) > max(idx_i, piv_i, val_i):
                    idx_val = r[idx_i].strip()
                    piv_val = r[piv_i].strip()
                    try:
                        num_val = float(r[val_i].replace(",", "").replace("$", ""))
                    except ValueError:
                        continue
                        
                    all_pivot_keys.add(piv_val)
                    if idx_val not in pivot_data:
                        pivot_data[idx_val] = {}
                    if piv_val not in pivot_data[idx_val]:
                        pivot_data[idx_val][piv_val] = []
                    pivot_data[idx_val][piv_val].append(num_val)
                    
            sorted_pivot_cols = sorted(list(all_pivot_keys))
            pivot_rows = []
            func = agg_func.upper()
            
            for idx_val, piv_dict in sorted(pivot_data.items()):
                row_dict = {index_col: idx_val}
                for p_col in sorted_pivot_cols:
                    vals = piv_dict.get(p_col, [])
                    if not vals:
                        row_dict[p_col] = 0.0
                    elif func == "SUM":
                        row_dict[p_col] = round(sum(vals), 2)
                    elif func in ["AVG", "MEAN"]:
                        row_dict[p_col] = round(sum(vals) / len(vals), 2)
                    elif func == "COUNT":
                        row_dict[p_col] = len(vals)
                    elif func == "MAX":
                        row_dict[p_col] = max(vals)
                    elif func == "MIN":
                        row_dict[p_col] = min(vals)
                pivot_rows.append(row_dict)
                
            return {
                "success": True,
                "index_column": index_col,
                "pivot_column": pivot_col,
                "value_column": value_col,
                "aggregation": func,
                "columns": [index_col] + sorted_pivot_cols,
                "rows": pivot_rows
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to build pivot table: {str(e)}"}
