import os
import ast
import json
from typing import Dict, List, Any, Optional

IGNORE_DIRS = {
    ".git", "__pycache__", "venv", ".venv", "env", "node_modules", 
    ".nava", "build", "dist", "receipts", ".pytest_cache", ".idea", ".vscode", "scratch"
}

IGNORE_EXTS = {
    ".pyc", ".pyo", ".pyd", ".png", ".jpg", ".jpeg", ".gif", ".ico", 
    ".pdf", ".docx", ".pptx", ".zip", ".tar", ".gz", ".exe", ".dll", ".so"
}

class ProjectIndexer:
    """
    Lightweight AST and File Tree indexer for NAVA workspaces.
    Scans codebases and generates structured symbol tables and file hierarchy.
    """
    def __init__(self, root_dir: str):
        self.root_dir = os.path.abspath(root_dir)
        self.nava_dir = os.path.join(self.root_dir, ".nava")
        self.index_path = os.path.join(self.nava_dir, "project_index.json")

    def build_index(self) -> Dict[str, Any]:
        """Scans the project directory and generates a comprehensive symbol and file index."""
        os.makedirs(self.nava_dir, exist_ok=True)
        
        file_tree = []
        symbols = []
        tech_stack = set()
        
        for root, dirs, files in os.walk(self.root_dir):
            # Prune ignored directories in-place
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
            
            for file in files:
                _, ext = os.path.splitext(file)
                if ext in IGNORE_EXTS or file.startswith("."):
                    continue
                    
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, self.root_dir).replace("\\", "/")
                
                try:
                    size = os.path.getsize(full_path)
                except Exception:
                    size = 0
                    
                file_info = {
                    "path": rel_path,
                    "filename": file,
                    "extension": ext,
                    "size_bytes": size
                }
                
                # Detect Tech Stack & Entry Points
                if file in ["main.py", "app.py", "nava_shell.py"]:
                    file_info["is_entry_point"] = True
                if file in ["requirements.txt", "pyproject.toml", "setup.py"] or ext == ".py":
                    tech_stack.add("Python")
                if file in ["package.json", "tsconfig.json"] or ext in [".js", ".ts", ".jsx", ".tsx"]:
                    tech_stack.add("JavaScript/TypeScript")
                if file in ["Dockerfile", "docker-compose.yml"]:
                    tech_stack.add("Docker")
                if file.endswith((".html", ".css")):
                    tech_stack.add("HTML/CSS")
                if file.endswith(".sql"):
                    tech_stack.add("SQL")
                    
                # AST Parsing for Python Files
                if ext == ".py":
                    file_symbols = self._parse_python_ast(full_path, rel_path)
                    symbols.extend(file_symbols)
                    file_info["symbol_count"] = len(file_symbols)
                    
                file_tree.append(file_info)
                
        index_data = {
            "root_dir": self.root_dir,
            "total_files": len(file_tree),
            "tech_stack": sorted(list(tech_stack)),
            "files": file_tree,
            "symbols": symbols
        }
        
        try:
            with open(self.index_path, "w", encoding="utf-8") as f:
                json.dump(index_data, f, indent=2)
        except Exception as e:
            print(f"[ProjectIndexer] Warning: Failed to save index file: {e}")
            
        return index_data

    def _parse_python_ast(self, full_path: str, rel_path: str) -> List[Dict[str, Any]]:
        """Extracts top-level and class-level functions, classes, and docstrings via AST."""
        symbols = []
        try:
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
            tree = ast.parse(source, filename=rel_path)
        except Exception:
            return symbols

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                doc = ast.get_docstring(node) or ""
                symbols.append({
                    "name": node.name,
                    "kind": "class",
                    "file": rel_path,
                    "line": node.lineno,
                    "docstring": doc.strip()[:200]
                })
                # Check methods inside class
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_doc = ast.get_docstring(item) or ""
                        symbols.append({
                            "name": f"{node.name}.{item.name}",
                            "kind": "method",
                            "file": rel_path,
                            "line": item.lineno,
                            "docstring": method_doc.strip()[:200]
                        })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node) or ""
                symbols.append({
                    "name": node.name,
                    "kind": "function",
                    "file": rel_path,
                    "line": node.lineno,
                    "docstring": doc.strip()[:200]
                })
        return symbols

    def search_symbols(self, query: str) -> List[Dict[str, Any]]:
        """Finds matching functions, methods, or classes matching a query string."""
        if not os.path.exists(self.index_path):
            self.build_index()
            
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return []
            
        q = query.lower().strip()
        results = []
        for s in data.get("symbols", []):
            if q in s.get("name", "").lower() or q in s.get("docstring", "").lower():
                results.append(s)
        return results

    def get_summary(self) -> Dict[str, Any]:
        """Returns high-level summary of the workspace index."""
        if not os.path.exists(self.index_path):
            return self.build_index()
        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "root_dir": data.get("root_dir", self.root_dir),
                "total_files": data.get("total_files", 0),
                "tech_stack": data.get("tech_stack", []),
                "total_symbols": len(data.get("symbols", []))
            }
        except Exception:
            return self.build_index()
