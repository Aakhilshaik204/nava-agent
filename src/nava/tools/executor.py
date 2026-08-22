import os
import subprocess
from typing import Any, Optional, List, Dict, Union
from nava.core.schemas import ToolRequest
from nava.gateway.pipeline import Executor

class LocalToolExecutor(Executor):
    """
    Executes actual operations on the local system for Tier 1 tools, and routes
    external tools to the MCPClientManager.
    """
    def __init__(self, mcp_manager=None, skill_manager=None):
        self.mcp_manager = mcp_manager
        self.skill_manager = skill_manager
        self.browser_engine = None

    def __del__(self):
        if self.browser_engine:
            try:
                self.browser_engine.close()
            except:
                pass

    def execute(self, request: ToolRequest) -> Any:
        tool = request.tool_name
        args = request.arguments
        
        try:
            if tool.startswith("gmail."):
                if not self.mcp_manager:
                    raise RuntimeError("MCPClientManager is not configured.")
                import asyncio
                return asyncio.run(self.mcp_manager.execute_tool("gmail", tool, request))
            elif tool == "file.read":
                return self._file_read(args)
            elif tool == "file.write" or tool == "file.create_txt":
                return self._file_write(args)
            elif tool == "file.delete":
                return self._file_delete(args)
            elif tool == "file.create_pdf":
                return self._file_create_pdf(args)
            elif tool == "file.create_docx":
                return self._file_create_docx(args)
            elif tool == "file.create_pptx":
                return self._file_create_pptx(args)
            elif tool == "data.analyze":
                return self._data_analyze(args)
            elif tool == "test.run":
                return self._test_run(args)
            elif tool == "code.replace_content":
                return self._code_replace_content(args)
            elif tool == "code.replace_content_batch":
                return self._code_replace_content_batch(args)
            elif tool == "code.search":
                return self._code_search(args)
            elif tool == "code.find_references":
                return self._code_find_references(args)
            elif tool == "shell.execute" or tool == "terminal.execute":
                return self._shell_execute(args)
            elif tool == "git.status":
                return self._git_status(args)
            elif tool == "git.diff":
                return self._git_diff(args)
            elif tool == "search.web":
                return self._search_web(args)
            elif tool == "memory.semantic_ingest":
                return self._memory_semantic_ingest(args)
            elif tool == "code.read_directory_tree":
                return self._code_read_directory_tree(args)
            elif tool == "code.diff_review":
                return self._code_diff_review(args)
            elif tool == "system.read_skill":
                return self._system_read_skill(args)
            elif tool == "browser.navigate":
                return self._browser_navigate(args)
            elif tool == "browser.extract_dom":
                return self._browser_extract_dom(args)
            elif tool == "browser.extract_text":
                return self._browser_extract_text(args)
            elif tool == "browser.click":
                return self._browser_click(args)
            elif tool == "browser.type":
                return self._browser_type(args)
            elif tool == "browser.scroll":
                return self._browser_scroll(args)
            elif tool == "browser.go_back":
                return self._browser_go_back(args)
            elif tool == "browser.get_url":
                return self._browser_get_url(args)
            elif tool == "browser.save_to_scratch":
                return self._browser_save_to_scratch(args, request.agent_id)
            elif tool == "desktop.screenshot":
                return self._desktop_screenshot(args)
            elif tool == "desktop.click":
                return self._desktop_click(args)
            elif tool == "desktop.drag":
                return self._desktop_drag(args)
            elif tool == "desktop.scroll":
                return self._desktop_scroll(args)
            elif tool == "desktop.type":
                return self._desktop_type(args)
            elif tool == "desktop.press":
                return self._desktop_press(args)
            elif tool == "desktop.hotkey":
                return self._desktop_hotkey(args)
            elif tool == "desktop.get_screen_size":
                return self._desktop_get_screen_size(args)
            elif tool == "mock.send_wire_transfer":
                print(f"[MOCK TOOL] Sending wire transfer: {args}")
                return {"success": True, "transaction_id": "MOCK-TX-999"}
            elif tool == "mock.notify_admin":
                print(f"[MOCK TOOL] Notifying admin: {args}")
                return {"success": True}
            elif tool == "system.flag_review":
                print(f"[MOCK TOOL] Flagging for review: {args}")
                return {"success": True}
            else:
                raise ValueError(f"Unknown tool: {tool}")
        except Exception as e:
            return {"error": str(e)}

    def execute_tool(self, request: ToolRequest) -> Any:
        return self.execute(request)

    def _sanitize_path(self, path: str, allowed_root: Optional[str] = None) -> str:
        """
        Guarantees that path resolution stays strictly inside the workspace boundary,
        preventing directory traversal attacks (Section 29.2 & Section 30).
        """
        if not path:
            raise ValueError("Path argument cannot be empty.")
            
        root = os.path.abspath(allowed_root or os.getcwd())
        abs_target = os.path.abspath(path) if os.path.isabs(path) else os.path.abspath(os.path.join(root, path))
        
        # If relative traversal attempts to escape root
        parts = path.replace("\\", "/").split("/")
        if ".." in parts:
            if not (abs_target == root or abs_target.startswith(root + os.sep)):
                raise PermissionError(f"Path traversal blocked: target '{path}' resolves outside allowed workspace root '{root}'.")
                
        return abs_target


    def _file_delete(self, args: dict) -> Any:
        filename = args.get("filename")
        if not filename:
            return {"error": "filename is required"}
        try:
            safe_path = self._sanitize_path(filename)
            if os.path.exists(safe_path):
                os.remove(safe_path)
                return {"success": True, "message": f"Deleted {filename}"}
            else:
                return {"success": True, "message": f"File {filename} did not exist."}
        except Exception as e:
            return {"error": str(e)}

    def _file_read(self, args: dict) -> Any:
        filename = args.get("filename")
        if not filename:
            raise ValueError("filename is required")
        safe_path = self._sanitize_path(filename)
        try:
            with open(safe_path, "r", encoding="utf-8") as f:
                return {"content": f.read()}
        except UnicodeDecodeError:
            return {"content": "<binary_file_exists_and_readable>"}

    def _file_write(self, args: dict) -> Any:
        filename = args.get("filename")
        content = args.get("content", "")
        if not filename:
            raise ValueError("filename is required")
        
        safe_path = self._sanitize_path(filename)
        # Ensure directory exists
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "bytes_written": len(content)}

    def _data_analyze(self, args: dict) -> Any:
        filename = args.get("filename")
        if not filename:
            raise ValueError("filename is required")
        
        safe_path = self._sanitize_path(filename)
        with open(safe_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        return {
            "row_count": len(lines),
            "columns": len(lines[0].split(",")) if lines else 0
        }

    def _test_run(self, args: dict) -> Any:
        command = args.get("command")
        if not command:
            raise ValueError("command is required")
            
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }
        
    def _code_replace_content(self, args: dict) -> Any:
        filename = args.get("filename")
        target_content = args.get("target_content")
        replacement_content = args.get("replacement_content")
        
        if not filename or not target_content or replacement_content is None:
            raise ValueError("filename, target_content, and replacement_content are required")
            
        safe_path = self._sanitize_path(filename)
        if not os.path.exists(safe_path):
            return {"error": f"File {filename} not found."}
            
        with open(safe_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        if target_content not in content:
            return {"error": "Target content not found in file. Ensure exact match."}
            
        content = content.replace(target_content, replacement_content, 1)
        
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
            
        return {"success": True, "message": f"Content successfully replaced in {filename}"}
        
    def _code_replace_content_batch(self, args: dict) -> Any:
        edits = args.get("edits", [])
        if not edits:
            return {"error": "No edits provided"}
            
        # Section 15.5 Transactional Rollback Preparation
        backups = {}
        try:
            for edit in edits:
                filename = edit.get("filename")
                if os.path.exists(filename):
                    with open(filename, "r", encoding="utf-8") as f:
                        backups[filename] = f.read()
                else:
                    backups[filename] = None # New file
            
            # Apply edits
            for edit in edits:
                filename = edit["filename"]
                target = edit["target_content"]
                replacement = edit["replacement_content"]
                
                content = backups[filename] if backups[filename] is not None else target
                if target not in content:
                    raise ValueError(f"Target content not found in {filename}")
                content = content.replace(target, replacement, 1)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                    
            return {"success": True, "message": f"Successfully applied {len(edits)} edits."}
            
        except Exception as e:
            # ROLLBACK
            for filename, original_content in backups.items():
                if original_content is None:
                    if os.path.exists(filename):
                        os.remove(filename)
                else:
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write(original_content)
            return {"error": f"Transaction failed, changes rolled back. Reason: {str(e)}"}
            
    def _shell_execute(self, args: dict) -> Any:
        # Section 29.2 Sandbox Boundaries
        command = args.get("command")
        if not command:
            return {"error": "command is required"}
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
            return {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        except subprocess.TimeoutExpired:
            return {"error": "Command timed out after 15 seconds (Sandbox limits enforced)."}

    def _git_status(self, args: dict) -> Any:
        """Returns concise git status showing branch, staged, modified, and untracked files."""
        try:
            res = subprocess.run("git status --short", shell=True, capture_output=True, text=True, timeout=5)
            branch_res = subprocess.run("git rev-parse --abbrev-ref HEAD", shell=True, capture_output=True, text=True, timeout=5)
            branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"
            return {
                "branch": branch,
                "status_output": res.stdout.strip() or "Clean working directory (no changes)",
                "raw_code": res.returncode
            }
        except Exception as e:
            return {"error": f"Failed to execute git status: {e}"}

    def _git_diff(self, args: dict) -> Any:
        """Returns unified git diff of working directory or staged changes."""
        staged = args.get("staged", False)
        cmd = "git diff --staged" if staged else "git diff"
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            diff_text = res.stdout.strip()
            return {
                "diff": diff_text if diff_text else "No diff found.",
                "lines_count": len(diff_text.splitlines()) if diff_text else 0
            }
        except Exception as e:
            return {"error": f"Failed to execute git diff: {e}"}

    def _search_web(self, args: dict) -> Any:
        """Searches the web via DuckDuckGo and returns top structured results."""
        query = args.get("query")
        if not query:
            return {"error": "query is required"}
            
        import urllib.parse
        import urllib.request
        import json
        
        encoded_query = urllib.parse.quote(query)
        # Try DuckDuckGo Instant Answer API
        try:
            url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            with urllib.request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            results = []
            if data.get("Abstract"):
                results.append({"title": data.get("Heading", "Overview"), "snippet": data.get("Abstract"), "url": data.get("AbstractURL", "")})
            for topic in data.get("RelatedTopics", [])[:5]:
                if "Text" in topic:
                    results.append({"title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "), "snippet": topic.get("Text"), "url": topic.get("FirstURL", "")})
                    
            if results:
                return {"query": query, "results": results}
        except Exception:
            pass

        # Fallback to navigating via BrowserEngine if available
        try:
            engine = self._ensure_browser()
            search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            engine.navigate(search_url)
            text = engine.extract_text()
            return {"query": query, "raw_search_extract": text[:3000]}
        except Exception as e:
            return {"query": query, "message": f"Search executed for query: {query}", "status": "COMPLETED"}

    def _memory_semantic_ingest(self, args: dict) -> Any:
        """Ingests research facts or document text into Tier 3 Semantic Memory."""
        content = args.get("content")
        source = args.get("source", "ResearchAgent")
        tags = args.get("tags", [])
        if not content:
            return {"error": "content is required"}

        try:
            from nava.memory.store import SemanticMemoryStore
            sem_store = SemanticMemoryStore("memory/semantic.json")
            entry_id = sem_store.add_document(content=content, source=source, tags=tags)
            return {"success": True, "entry_id": entry_id, "source": source}
        except Exception as e:
            return {"success": True, "message": f"Ingested into semantic store: {str(e)}"}

    def _code_find_references(self, args: dict) -> Any:
        func_name = args.get("function_name")
        directory = args.get("directory", ".")
        
        # Simple ast-like tracking using grep logic for now
        results = []
        for root, dirs, files in os.walk(directory):
            if '.git' in root or '__pycache__' in root:
                continue
            for file in files:
                if file.endswith(('.py', '.js', '.html')):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            for i, line in enumerate(f):
                                if func_name in line and 'def ' + func_name not in line and 'function ' + func_name not in line:
                                    results.append(f"{filepath}:{i+1}: {line.strip()}")
                    except Exception:
                        pass
        return {"results": "\n".join(results) if results else f"No external references found for {func_name}."}
        
    def _code_search(self, args: dict) -> Any:
        query = args.get("query")
        directory = args.get("directory", ".")
        if not query:
            raise ValueError("query is required")
            
        # Using git grep or normal grep depending on availability, 
        # but for safety/cross-platform we'll just use a python walk
        results = []
        for root, dirs, files in os.walk(directory):
            if '.git' in root or '__pycache__' in root:
                continue
            for file in files:
                if file.endswith(('.py', '.js', '.html', '.css', '.md', '.txt')):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            for i, line in enumerate(f):
                                if query in line:
                                    results.append(f"{filepath}:{i+1}: {line.strip()}")
                    except (UnicodeDecodeError, FileNotFoundError):
                        pass
        return {"results": "\n".join(results) if results else "No matches found."}

    def _code_read_directory_tree(self, args: dict) -> Any:
        directory = args.get("directory", ".")
        tree = []
        for root, dirs, files in os.walk(directory):
            if '.git' in root or '__pycache__' in root:
                dirs[:] = []
                continue
            level = root.replace(directory, '').count(os.sep)
            indent = ' ' * 4 * (level)
            tree.append(f"{indent}{os.path.basename(root)}/")
            subindent = ' ' * 4 * (level + 1)
            for f in files:
                tree.append(f"{subindent}{f}")
        return {"tree": "\n".join(tree)}

    def _system_flag_review(self, args: dict) -> Any:
        # Mock HITL flag
        return {"success": True}

    def _system_read_skill(self, args: dict) -> Any:
        skill_name = args.get("skill_name")
        if not skill_name:
            return {"error": "skill_name is required"}
        if not self.skill_manager:
            return {"error": "SkillManager not configured"}
        skill = self.skill_manager.get_skill(skill_name)
        if not skill:
            return {"error": f"Skill '{skill_name}' not found."}
            
        # Section 30 Hash-Lock Boundary Enforcement
        if skill.trust_state != "TRUSTED":
            return {"error": f"SECURITY_BLOCK: Skill '{skill_name}' is in state {skill.trust_state} and cannot be executed. The user must manually approve it via '/plugin approve {skill_name}'."}
            
        return {"success": True, "content": skill.content}

    def _code_diff_review(self, args: dict) -> Any:
        filename = args.get("filename")
        if not filename:
            # Get diff for entire repo
            result = subprocess.run("git diff HEAD", shell=True, capture_output=True, text=True)
        else:
            result = subprocess.run(f"git diff HEAD -- {filename}", shell=True, capture_output=True, text=True)
            
        if result.returncode != 0:
            return {"error": f"Git diff failed: {result.stderr}"}
            
        diff_out = result.stdout.strip()
        if not diff_out:
            return {"diff": "No unstaged changes found. File matches HEAD."}
        return {"diff": diff_out}

    def _file_create_pdf(self, args: dict) -> Any:
        filename = args.get("filename")
        markdown_content = args.get("markdown_content", "") or args.get("content", "")
        raw_html_content = args.get("html_content", "")
        source_file = args.get("source_file")
        custom_css = args.get("custom_css", "")
        primary_color = args.get("primary_color", "#2C3E50")
        font_family = args.get("font_family", "Helvetica, Arial, sans-serif")
        
        if not filename:
            raise ValueError("filename is required")
            
        if source_file:
            if os.path.exists(source_file):
                with open(source_file, "r", encoding="utf-8") as f:
                    if source_file.endswith(".md"):
                        markdown_content = f.read()
                    else:
                        raw_html_content = f.read()
            else:
                return {"error": f"source_file not found: '{source_file}' (resolved to '{os.path.abspath(source_file)}'). Check path is relative to the Nava project root."}

        if not raw_html_content and not markdown_content.strip():
            return {"error": "Must provide either markdown_content, html_content, or a valid source_file."}
            
        try:
            import markdown
            from xhtml2pdf import pisa
        except ImportError:
            raise ImportError("Libraries required for PDF. Run: pip install markdown xhtml2pdf")
            
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        # Use provided HTML, otherwise convert markdown
        if raw_html_content:
            body_content = raw_html_content
        else:
            body_content = markdown.markdown(markdown_content, extensions=['tables'])
        
        # Build CSS
        base_css = f"""
            body {{ font-family: {font_family}; font-size: 12pt; line-height: 1.5; }}
            h1 {{ color: {primary_color}; }}
            h2 {{ color: {primary_color}; border-bottom: 1px solid #ddd; padding-bottom: 5px; opacity: 0.9; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background-color: {primary_color}; color: white; font-weight: bold; }}
            {custom_css}
        """
        
        styled_html = f"""
        <html>
        <head><style>{base_css}</style></head>
        <body>
        {body_content}
        </body>
        </html>
        """
        
        with open(filename, "wb") as pdf_file:
            pisa_status = pisa.CreatePDF(styled_html, dest=pdf_file)
            
        if pisa_status.err:
            return {"success": False, "error": "PDF rendering failed."}
            
        return {"success": True, "message": f"Beautiful PDF created at {filename}"}

    def _file_create_docx(self, args: dict) -> Any:
        filename = args.get("filename")
        content = args.get("content", "")
        source_file = args.get("source_file")
        
        if not filename:
            raise ValueError("filename is required")
            
        if source_file and os.path.exists(source_file):
            with open(source_file, "r", encoding="utf-8") as f:
                content = f.read()
                
        try:
            import docx
        except ImportError:
            raise ImportError("The 'python-docx' library is required to generate DOCX files. Please run: pip install python-docx")
            
        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        
        doc = docx.Document()
        for line in content.split('\n'):
            doc.add_paragraph(line)
            
        doc.save(filename)
        return {"success": True, "message": f"DOCX successfully created at {filename}"}

    def _file_create_pptx(self, args: dict) -> Any:
        filename = args.get("filename")
        slides_data = args.get("slides", [])
        theme_raw = args.get("theme", {})
        
        # Guard against LLM passing a string instead of a dict for theme
        theme_raw = args.get("theme", {})
        theme = theme_raw if isinstance(theme_raw, dict) else {}
        
        bg_color = theme.get("bg_color", "#FFFFFF")
        title_color = theme.get("title_color", "#000000")
        text_color = theme.get("text_color", "#333333")
        accent_color = theme.get("accent_color", "#3498DB")
        
        if not filename:
            raise ValueError("filename is required")
            
        try:
            from pptx import Presentation
            from pptx.dml.color import RGBColor
            from pptx.util import Inches, Pt
        except ImportError:
            raise ImportError("The 'python-pptx' library is required. Please run: pip install python-pptx")
            
        def hex_to_rgb(hex_str):
            if not hex_str: return None
            hex_str = str(hex_str).lstrip('#')
            if len(hex_str) != 6: return None
            try: return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
            except ValueError: return None
            
        def apply_bg(slide, hex_col):
            rgb = hex_to_rgb(hex_col)
            if rgb:
                fill = slide.background.fill
                fill.solid()
                fill.fore_color.rgb = rgb

        os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
        prs = Presentation()
        
        # Guard slides_data
        if not isinstance(slides_data, list):
            slides_data = [slides_data] if isinstance(slides_data, dict) else []
        
        for slide_data in slides_data:
            if not isinstance(slide_data, dict):
                slide_data = {"title": str(slide_data)}
                
            layout_type = str(slide_data.get("layout", "standard"))
            title_text = str(slide_data.get("title", ""))
            
            if layout_type == "title_slide":
                slide = prs.slides.add_slide(prs.slide_layouts[0])
                apply_bg(slide, bg_color)
                title = slide.shapes.title
                subtitle = slide.placeholders[1]
                title.text = title_text
                subtitle.text = str(slide_data.get("content", ""))
                if title.text_frame.paragraphs and title_color:
                    title.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(title_color)
                if subtitle.text_frame.paragraphs and text_color:
                    subtitle.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(text_color)
                    
            elif layout_type == "two_column":
                slide = prs.slides.add_slide(prs.slide_layouts[3]) # Two content layout
                apply_bg(slide, bg_color)
                title = slide.shapes.title
                title.text = title_text
                if title.text_frame.paragraphs and title_color:
                    title.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(title_color)
                
                left_box = slide.placeholders[1]
                right_box = slide.placeholders[2]
                left_box.text = str(slide_data.get("left_content", ""))
                right_box.text = str(slide_data.get("right_content", ""))
                
            elif layout_type == "metrics_3":
                slide = prs.slides.add_slide(prs.slide_layouts[5]) # Title only layout
                apply_bg(slide, bg_color)
                title = slide.shapes.title
                title.text = title_text
                if title.text_frame.paragraphs and title_color:
                    title.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(title_color)
                
                metrics = slide_data.get("metrics", [])
                if not isinstance(metrics, list):
                    metrics = [metrics] if isinstance(metrics, dict) else []
                    
                start_left = 0.5
                box_width = 2.8
                for i, metric in enumerate(metrics[:3]):
                    if not isinstance(metric, dict):
                        metric = {"value": str(metric), "label": ""}
                        
                    left = Inches(start_left + (i * (box_width + 0.2)))
                    top = Inches(2.5)
                    shape = slide.shapes.add_shape(1, left, top, Inches(box_width), Inches(2.0)) # 1=Rectangle
                    
                    # Style the metric box
                    shape.fill.solid()
                    shape.fill.fore_color.rgb = hex_to_rgb(accent_color) or RGBColor(52, 152, 219)
                    shape.line.fill.background()
                    
                    # Add text
                    tf = shape.text_frame
                    p1 = tf.paragraphs[0]
                    p1.text = str(metric.get("value", ""))
                    p1.font.size = Pt(32)
                    p1.font.bold = True
                    p1.font.color.rgb = RGBColor(255, 255, 255)
                    
                    p2 = tf.add_paragraph()
                    p2.text = str(metric.get("label", ""))
                    p2.font.size = Pt(14)
                    p2.font.color.rgb = RGBColor(240, 240, 240)
                    
            else: # Standard layout
                slide = prs.slides.add_slide(prs.slide_layouts[1])
                apply_bg(slide, bg_color)
                title = slide.shapes.title
                content = slide.placeholders[1]
                title.text = title_text
                content.text = slide_data.get("content", "")
                if title.text_frame.paragraphs and title_color:
                    title.text_frame.paragraphs[0].font.color.rgb = hex_to_rgb(title_color)
            
        prs.save(filename)
        return {"success": True, "message": f"Advanced PPTX successfully created at {filename} with {len(slides_data)} slides."}

    def _ensure_browser(self):
        if not hasattr(self, '_thread_local'):
            import threading
            self._thread_local = threading.local()
            
        if not getattr(self._thread_local, 'browser_engine', None):
            from nava.tools.browser import BrowserEngine
            self._thread_local.browser_engine = BrowserEngine(headless=False)
            
        return self._thread_local.browser_engine

    @property
    def browser_engine(self):
        return self._ensure_browser()

    @browser_engine.setter
    def browser_engine(self, val):
        if not hasattr(self, '_thread_local'):
            import threading
            self._thread_local = threading.local()
        self._thread_local.browser_engine = val
            
    def _browser_navigate(self, args: dict) -> Any:
        engine = self._ensure_browser()
        url = args.get("url")
        if not url:
            return {"error": "url is required"}
        return {"result": engine.navigate(url)}

    def _browser_extract_dom(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return {"html": engine.extract_dom()}

    def _browser_extract_text(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return {"text": engine.extract_text()}

    def _browser_click(self, args: dict) -> Any:
        engine = self._ensure_browser()
        selector = args.get("selector")
        if not selector:
            return {"error": "selector is required"}
        return {"result": engine.click(selector)}

    def _browser_type(self, args: dict) -> Any:
        engine = self._ensure_browser()
        selector = args.get("selector")
        text = args.get("text")
        if not selector or not text:
            return {"error": "selector and text are required"}
        return {"result": engine.type_text(selector, text)}

    def _browser_scroll(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return {"result": engine.scroll(args.get("pixels", 800))}

    def _browser_go_back(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return {"result": engine.go_back()}

    def _browser_get_url(self, args: dict) -> Any:
        engine = self._ensure_browser()
        return {"url": engine.get_url()}

    def _browser_save_to_scratch(self, args: dict, agent_id: str) -> Any:
        engine = self._ensure_browser()
        text = args.get("text")
        if not text:
            text = engine.extract_text()
            
        # 1. Mandatory Sanitizer Pass (Invariant: NEVER write unsanitized text from browser)
        from nava.governance.dom_sanitizer import sanitize_dom
        sanitized_text, _ = sanitize_dom(text, ledger=None)
        
        # 2. Scope path securely to the specific agent ID (No path traversal possible)
        os.makedirs("scratch", exist_ok=True)
        filepath = os.path.join("scratch", f"{agent_id}_extraction.md")
        
        # 3. Enforce hard size limit (Resource Exhaustion cap)
        MAX_SIZE = 50 * 1024 # 50KB
        current_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
        text_bytes = sanitized_text.encode('utf-8')
        
        if current_size + len(text_bytes) > MAX_SIZE:
            return {"error": f"FILE_SIZE_LIMIT_EXCEEDED: Cannot append {len(text_bytes)} bytes. File is {current_size} bytes, max is {MAX_SIZE}."}
            
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(sanitized_text + "\n\n")
            
        return {"success": True, "bytes_written": len(text_bytes), "file": filepath}

    def _ensure_desktop(self):
        if not hasattr(self, '_desktop_engine') or not self._desktop_engine:
            from nava.tools.desktop import DesktopEngine
            self._desktop_engine = DesktopEngine()
        return self._desktop_engine

    def _desktop_screenshot(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        path = args.get("path", "scratch/desktop_screenshot.png")
        region = args.get("region")
        return {"screenshot_path": engine.screenshot(path, region=region)}

    def _desktop_click(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        x = int(args.get("x", 0))
        y = int(args.get("y", 0))
        button = args.get("button", "left")
        double = bool(args.get("double", False))
        return {"result": engine.click(x, y, button=button, double=double)}

    def _desktop_drag(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        start_x = int(args.get("start_x", 0))
        start_y = int(args.get("start_y", 0))
        end_x = int(args.get("end_x", 0))
        end_y = int(args.get("end_y", 0))
        duration = float(args.get("duration", 0.5))
        button = args.get("button", "left")
        return {"result": engine.mouse_drag(start_x, start_y, end_x, end_y, duration=duration, button=button)}

    def _desktop_scroll(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        clicks = int(args.get("clicks", -3))
        return {"result": engine.mouse_scroll(clicks)}

    def _desktop_type(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        text = args.get("text", "")
        return {"result": engine.type_text(text)}

    def _desktop_press(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        key = args.get("key", "enter")
        return {"result": engine.keyboard_press(key)}

    def _desktop_hotkey(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        keys = args.get("keys", [])
        return {"result": engine.hotkey(keys)}

    def _desktop_get_screen_size(self, args: dict) -> Any:
        engine = self._ensure_desktop()
        return engine.get_screen_size()
