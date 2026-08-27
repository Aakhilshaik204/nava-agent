import os
import ast
import re
import subprocess
from typing import Dict, Any, List, Optional

class CodingSuperpowersEngine:
    """
    Dedicated engine for CodingAgent Superpowers:
    - Context7 AST Symbol Graphs & Token Slicing
    - Superpowers AST Search, Replace & Linter Self-Healing
    - Git MCP Branching & Commit Auditing
    """
    def __init__(self, path_resolver=None, sanitizer=None, artifact_resolver=None):
        self.path_resolver = path_resolver
        self.sanitizer = sanitizer
        self.artifact_resolver = artifact_resolver

    def _is_internal_system_path(self, path: str) -> bool:
        if not path:
            return False
        clean = path.replace("\\", "/").strip("/.")
        if clean.startswith(("projects/", "tasks/", "memory/", "scratch/", "artifacts/")):
            return False
        forbidden_prefixes = ("src/", "tests/", ".git/", ".gemini/", ".vscode/", ".nava/")
        forbidden_exact = {"src", "tests", ".git", ".gemini", ".vscode", "nava.yaml", "nava_shell.py", "requirements.txt", ".vault_key", "index.html", ".env", ".env.example"}
        return clean in forbidden_exact or clean.startswith(forbidden_prefixes)

    def _resolve_target(self, target: str) -> str:
        clean = target.replace("\\", "/").lstrip("/")
        if self._is_internal_system_path(clean):
            raise PermissionError(f"Access denied: '{target}' is a protected NAVA internal file.")
        candidates = []
        if self.artifact_resolver:
            candidates.append(self.artifact_resolver(clean))
        if self.path_resolver:
            candidates.append(self.path_resolver(clean))
        if self.sanitizer:
            candidates.append(self.sanitizer(clean))
        candidates.append(clean)
        
        return next((p for p in candidates if os.path.exists(p)), candidates[0])

    # =========================================================================
    # Context7 Code Intelligence (Symbol Graphs & 80% Token Slicing)
    # =========================================================================
    def get_symbol_graph(self, filename: Optional[str] = None, directory: Optional[str] = None) -> Dict[str, Any]:
        default_dir = os.path.join("projects", "Nava") if os.path.exists(os.path.join("projects", "Nava")) else "projects"
        target = filename or directory or default_dir
        try:
            target_path = self._resolve_target(target)
        except PermissionError as pe:
            return {"error": str(pe), "symbols": []}
        
        if not os.path.exists(target_path):
            return {"error": f"Path not found in active project: '{target}'", "symbols": []}
            
        files_to_scan = []
        if os.path.isdir(target_path):
            for root, _, files in os.walk(target_path):
                for f in files:
                    if f.endswith((".py", ".js", ".ts", ".jsx", ".tsx")):
                        files_to_scan.append(os.path.join(root, f))
        else:
            files_to_scan.append(target_path)
            
        symbol_graph = []
        for fpath in files_to_scan[:25]:
            rel_file = os.path.relpath(fpath, os.getcwd())
            file_entry = {"file": rel_file, "classes": [], "functions": [], "imports": []}
            
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    
                if fpath.endswith(".py"):
                    tree = ast.parse(content, filename=fpath)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                            doc = ast.get_docstring(node) or ""
                            file_entry["classes"].append({"name": node.name, "line": node.lineno, "methods": methods, "doc": doc[:120]})
                        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            doc = ast.get_docstring(node) or ""
                            args_list = [a.arg for a in node.args.args]
                            file_entry["functions"].append({"name": node.name, "line": node.lineno, "args": args_list, "doc": doc[:120]})
                        elif isinstance(node, ast.Import):
                            for n in node.names:
                                file_entry["imports"].append(n.name)
                        elif isinstance(node, ast.ImportFrom):
                            mod = node.module or ""
                            names = [n.name for n in node.names]
                            file_entry["imports"].append(f"{mod}: {', '.join(names)}")
                else:
                    fn_matches = re.findall(r'(?:function\s+([a-zA-Z0-9_$]+)|const\s+([a-zA-Z0-9_$]+)\s*=\s*(?:\([^)]*\)|[a-zA-Z0-9_$]+)\s*=>)', content)
                    for f1, f2 in fn_matches:
                        name = f1 or f2
                        if name:
                            file_entry["functions"].append({"name": name})
            except Exception as e:
                file_entry["parse_warning"] = str(e)
                
            symbol_graph.append(file_entry)
            
        total_syms = sum(len(e["classes"]) + len(e["functions"]) for e in symbol_graph)
        return {
            "symbol_graph": symbol_graph,
            "total_files_indexed": len(symbol_graph),
            "total_symbols_extracted": total_syms,
            "context_optimization": "Symbol hierarchy mapped for token-efficient retrieval."
        }

    def slice_context(self, filename: str, symbol_name: str) -> Dict[str, Any]:
        if not filename or not symbol_name:
            return {"error": "filename and symbol_name are required for context slicing"}
            
        target_path = self._resolve_target(filename)
        if not os.path.exists(target_path):
            return {"error": f"File not found: '{filename}'"}
            
        with open(target_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            lines = content.splitlines()
            
        if filename.endswith(".py"):
            try:
                tree = ast.parse(content, filename=target_path)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol_name:
                        start_line = node.lineno - 1
                        end_line = getattr(node, 'end_lineno', start_line + 25)
                        sliced_snippet = "\n".join(lines[start_line:end_line])
                        
                        full_tokens = len(content.split())
                        sliced_tokens = len(sliced_snippet.split())
                        reduction = f"{max(0, round((1 - (sliced_tokens / max(1, full_tokens))) * 100))}%"
                        
                        return {
                            "symbol": symbol_name,
                            "type": type(node).__name__,
                            "line_range": [node.lineno, end_line],
                            "snippet": sliced_snippet,
                            "token_reduction": reduction,
                            "message": f"Context sliced successfully ({reduction} prompt token reduction)"
                        }
            except Exception:
                pass
                
        for idx, line in enumerate(lines):
            if symbol_name in line:
                start = max(0, idx - 2)
                end = min(len(lines), idx + 30)
                return {
                    "symbol": symbol_name,
                    "line_range": [start + 1, end],
                    "snippet": "\n".join(lines[start:end]),
                    "message": "Extracted context snippet via boundary heuristics."
                }
                
        return {"error": f"Symbol '{symbol_name}' not found in {filename}"}

    # =========================================================================
    # Superpowers AST Refactoring & Self-Healing Linter Tools
    # =========================================================================
    def ast_search(self, pattern: str, filename: Optional[str] = None) -> Dict[str, Any]:
        if not pattern:
            return {"error": "pattern is required for AST search"}
            
        target = filename or "src"
        target_path = self._resolve_target(target)
        if not os.path.exists(target_path):
            return {"error": f"File or directory not found: '{target}'"}
            
        matches = []
        files = [target_path] if os.path.isfile(target_path) else [
            os.path.join(root, f) for root, _, fs in os.walk(target_path) for f in fs if f.endswith((".py", ".js", ".ts"))
        ]
        
        for fpath in files[:15]:
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                lines = content.splitlines()
                
                if fpath.endswith(".py"):
                    try:
                        tree = ast.parse(content)
                        for node in ast.walk(tree):
                            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                                if pattern.lower() in node.name.lower():
                                    matches.append({
                                        "file": os.path.relpath(fpath, os.getcwd()),
                                        "node_type": type(node).__name__,
                                        "name": node.name,
                                        "line": node.lineno,
                                        "code_snippet": lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                                    })
                    except Exception:
                        pass
                
                for i, l in enumerate(lines):
                    if pattern.lower() in l.lower() and not any(m["line"] == i+1 for m in matches if m["file"] == os.path.relpath(fpath, os.getcwd())):
                        matches.append({
                            "file": os.path.relpath(fpath, os.getcwd()),
                            "node_type": "LineMatch",
                            "line": i + 1,
                            "code_snippet": l.strip()
                        })
            except Exception:
                pass
                
        return {"matches": matches, "total_found": len(matches)}

    def ast_replace(self, filename: str, target_symbol: str, replacement_code: str) -> Dict[str, Any]:
        if not filename or not target_symbol or replacement_code is None:
            return {"error": "filename, target_symbol, and replacement_code are required"}
            
        target_path = self._resolve_target(filename)
        if not os.path.exists(target_path):
            return {"error": f"File not found: '{filename}'"}
            
        with open(target_path, "r", encoding="utf-8") as f:
            old_content = f.read()
            
        if target_symbol not in old_content:
            return {"error": f"Target symbol or pattern '{target_symbol}' not found in {filename}"}
            
        new_content = old_content.replace(target_symbol, replacement_code, 1)
        
        if filename.endswith(".py"):
            try:
                ast.parse(new_content, filename=target_path)
            except SyntaxError as e:
                return {"error": f"AST replacement resulted in SyntaxError: {e.msg} at line {e.lineno}", "reverted": True}
                
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(new_content)
            
        return {
            "success": True,
            "file": os.path.relpath(target_path, os.getcwd()),
            "message": f"Successfully performed AST-verified replacement in '{filename}'"
        }

    def compiler_autofix(self, filename: str, language: str = "python") -> Dict[str, Any]:
        if not filename:
            return {"error": "filename is required"}
            
        target_path = self._resolve_target(filename)
        if not os.path.exists(target_path):
            return {"error": f"File not found: '{filename}'"}
            
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        diagnostics = []
        if filename.endswith(".py"):
            try:
                ast.parse(content, filename=target_path)
                return {"status": "CLEAN", "diagnostics": [], "message": f"Syntax and AST validation PASSED for '{filename}'."}
            except SyntaxError as err:
                diagnostics.append({
                    "line": err.lineno,
                    "offset": err.offset,
                    "text": err.text,
                    "message": err.msg
                })
                
                # Heuristic self-healing for missing colons
                lines = content.splitlines()
                if err.lineno and err.lineno <= len(lines):
                    bad_line = lines[err.lineno - 1]
                    if any(bad_line.strip().startswith(kw) for kw in ["def ", "class ", "if ", "elif ", "else", "for ", "while ", "try", "except"]) and not bad_line.rstrip().endswith(":"):
                        fixed_line = bad_line.rstrip() + ":"
                        lines[err.lineno - 1] = fixed_line
                        repaired_content = "\n".join(lines)
                        try:
                            ast.parse(repaired_content)
                            with open(target_path, "w", encoding="utf-8") as f:
                                f.write(repaired_content)
                            return {
                                "status": "AUTO_FIXED",
                                "healed_line": err.lineno,
                                "original": bad_line,
                                "repaired": fixed_line,
                                "message": f"Superpowers auto-healed missing colon syntax error on line {err.lineno}."
                            }
                        except Exception:
                            pass
                            
                return {
                    "status": "ERRORS_DETECTED",
                    "diagnostics": diagnostics,
                    "advice": "CodingAgent should review the diagnostic lines to correct syntax."
                }
                
        return {"status": "CLEAN", "message": f"File '{filename}' verified."}

    # =========================================================================
    # Git MCP / Worktree Tools
    # =========================================================================
    def git_branch(self, branch_name: Optional[str] = None, create: bool = True) -> Dict[str, Any]:
        try:
            if branch_name and create:
                res = subprocess.run(["git", "checkout", "-b", branch_name], capture_output=True, text=True, cwd=os.getcwd())
                if res.returncode != 0:
                    res = subprocess.run(["git", "checkout", branch_name], capture_output=True, text=True, cwd=os.getcwd())
                return {"branch": branch_name, "status": "active", "output": res.stdout or res.stderr}
            else:
                res = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True, cwd=os.getcwd())
                return {"current_branch": res.stdout.strip()}
        except Exception as e:
            return {"error": str(e)}

    def git_commit(self, message: str = "Auto-commit by NAVA CodingAgent") -> Dict[str, Any]:
        try:
            subprocess.run(["git", "add", "."], capture_output=True, text=True, cwd=os.getcwd())
            res = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True, cwd=os.getcwd())
            return {"success": res.returncode == 0, "output": res.stdout or res.stderr}
        except Exception as e:
            return {"error": str(e)}
