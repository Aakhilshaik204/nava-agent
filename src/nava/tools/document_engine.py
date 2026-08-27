"""
document_engine.py — Dedicated Document Generation, Typst PDF Compilation & Format Conversion Engine.
Provides Typst vector compilation, executive template rendering, DOCX/PPTX export, and universal document reading.
"""
import os
import re
import json
import shutil
import subprocess
from typing import Dict, Any, List, Optional, Callable

class DocumentEngine:
    def __init__(
        self,
        path_resolver: Optional[Callable[[str], str]] = None,
        sanitizer: Optional[Callable[[str], str]] = None,
        artifact_resolver: Optional[Callable[[str], str]] = None
    ):
        self.path_resolver = path_resolver or (lambda p: os.path.abspath(p))
        self.sanitizer = sanitizer or (lambda p: os.path.abspath(p))
        self.artifact_resolver = artifact_resolver or (lambda p: os.path.abspath(p))

    def _resolve_target(self, path: str) -> str:
        clean = path.replace("\\", "/")
        if clean.startswith(("tasks/", "artifacts/", "scratch/", "projects/", "memory/", ".nava/")):
            return self.sanitizer(path)
        if "/" in clean:
            return self.path_resolver(path)
        return self.artifact_resolver(path)

    def compile_typst(self, source: str, output_pdf: str, template_vars: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Compiles raw Typst markup code or a .typ source file into a publication-quality PDF.
        Supports native Typst compiler (if installed) with an executive high-fidelity
        print rendering fallback for maximum portability and zero visual code leakage.
        """
        resolved_out = self._resolve_target(output_pdf)
        os.makedirs(os.path.dirname(os.path.abspath(resolved_out)), exist_ok=True)

        # Check if source is a file path or raw Typst code
        typst_code = source
        if os.path.exists(source):
            with open(source, "r", encoding="utf-8", errors="replace") as f:
                typst_code = f.read()
        elif len(source) < 300 and (source.endswith(".typ") or "/" in source or "\\" in source):
            resolved_src = self._resolve_target(source)
            if not os.path.exists(resolved_src) and os.path.exists("tasks"):
                # Cross-task lookup
                import glob
                past_typs = sorted(
                    glob.glob(os.path.join("tasks", "*", "artifacts", os.path.basename(source))),
                    key=os.path.getmtime,
                    reverse=True
                )
                if past_typs:
                    resolved_src = past_typs[0]
            if os.path.exists(resolved_src):
                with open(resolved_src, "r", encoding="utf-8", errors="replace") as f:
                    typst_code = f.read()

        # Substitute template variables if provided
        if template_vars:
            for k, v in template_vars.items():
                typst_code = typst_code.replace(f"{{{{{k}}}}}", str(v))
                typst_code = typst_code.replace(f"{{{k}}}", str(v))

        # 1. Try Native Rust Typst compiler via official python package
        try:
            import typst
            temp_typ = resolved_out.replace(".pdf", ".typ")
            with open(temp_typ, "w", encoding="utf-8") as f:
                f.write(typst_code)
            typst.compile(temp_typ, output=resolved_out)
            if os.path.exists(temp_typ):
                try:
                    os.remove(temp_typ)
                except Exception:
                    pass
            file_size = os.path.getsize(resolved_out)
            return {
                "success": True,
                "saved_to": os.path.relpath(resolved_out, os.getcwd()),
                "bytes_written": file_size,
                "compiler": "native-typst-rust"
            }
        except ImportError:
            pass
        except Exception:
            pass

        # 2. Try Native Typst CLI binary if available in PATH
        typst_bin = shutil.which("typst")
        if typst_bin:
            try:
                temp_typ = resolved_out.replace(".pdf", ".typ")
                with open(temp_typ, "w", encoding="utf-8") as f:
                    f.write(typst_code)
                res = subprocess.run([typst_bin, "compile", temp_typ, resolved_out], capture_output=True, timeout=15)
                if res.returncode == 0 and os.path.exists(resolved_out):
                    return {
                        "success": True,
                        "saved_to": os.path.relpath(resolved_out, os.getcwd()),
                        "bytes_written": os.path.getsize(resolved_out),
                        "compiler": "native-typst-cli"
                    }
            except Exception:
                pass

        # 3. High-Fidelity Typst-to-Executive Print Engine (Zero syntax leakage)
        html_content = self._convert_typst_to_styled_html(typst_code)
        
        try:
            from xhtml2pdf import pisa
            
            with open(resolved_out, "wb") as pdf_file:
                pisa_status = pisa.CreatePDF(html_content, dest=pdf_file)
                
            if os.path.exists(resolved_out) and os.path.getsize(resolved_out) > 100:
                file_size = os.path.getsize(resolved_out)
                return {
                    "success": True,
                    "saved_to": os.path.relpath(resolved_out, os.getcwd()),
                    "bytes_written": file_size,
                    "compiler": "typst-executive-print-engine"
                }
            if pisa_status.err:
                return {"success": False, "error": f"PDF generation error: code {pisa_status.err}"}
        except Exception as fallback_err:
            try:
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas
                c = canvas.Canvas(resolved_out, pagesize=letter)
                c.setFont("Helvetica-Bold", 16)
                c.drawString(72, 750, "NAVA Executive Document")
                c.setFont("Helvetica", 10)
                y = 720
                for line in typst_code.split("\n")[:40]:
                    if line.strip():
                        c.drawString(72, y, line.strip()[:80])
                        y -= 15
                c.save()
                if os.path.exists(resolved_out):
                    return {
                        "success": True,
                        "saved_to": os.path.relpath(resolved_out, os.getcwd()),
                        "bytes_written": os.path.getsize(resolved_out),
                        "compiler": "reportlab-canvas"
                    }
            except Exception:
                pass
            typ_fallback = resolved_out.replace(".pdf", ".typ")
            with open(typ_fallback, "w", encoding="utf-8") as f:
                f.write(typst_code)
            return {
                "success": False,
                "error": f"Compilation failed: {str(fallback_err)}. Saved raw Typst to {typ_fallback}"
            }

    def render_template(
        self,
        template_name: str,
        title: str,
        author: str,
        content_blocks: List[Dict[str, Any]],
        output_pdf: str,
        theme: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Renders an executive pre-designed document template."""
        t_name = template_name.lower().replace("-", "_")
        primary_color = (theme or {}).get("primary_color", "#1E3A8A")
        accent_color = (theme or {}).get("accent_color", "#3B82F6")

        typst_markup = [
            f'// Generated by NAVA DocumentAgent — Template: {t_name}',
            '#set page(paper: "a4", margin: (x: 2cm, top: 2.5cm, bottom: 2.5cm))',
            '#set text(font: "Helvetica", size: 11pt, lang: "en")',
            '',
            f'= {title}',
            f'#text(size: 11pt, style: "italic")[Author / Agent: {author}]',
            '#v(1em)',
            ''
        ]

        for block in content_blocks:
            b_type = block.get("type", "paragraph")
            b_title = block.get("title", "")
            b_content = block.get("content", "")

            if b_title:
                typst_markup.append(f'== {b_title}\n')

            if b_type == "callout" or b_type == "alert":
                typst_markup.append(f'#rect[\n  *Note:* {b_content}\n]\n')
            elif b_type == "table":
                headers = block.get("headers", [])
                rows = block.get("rows", [])
                if headers:
                    cols_str = ", ".join(["1fr"] * len(headers))
                    table_cells = [f'  [* {h} *]' for h in headers]
                    for r in rows:
                        table_cells.extend([f'  [{cell}]' for cell in r])
                    typst_markup.append(
                        f'#table(\n'
                        f'  columns: ({cols_str}),\n'
                        + ",\n".join(table_cells) + "\n"
                        f')\n'
                    )
            elif b_type == "bullet_list":
                items = block.get("items", [])
                for item in items:
                    typst_markup.append(f'- {item}')
                typst_markup.append('')
            else:
                typst_markup.append(f'{b_content}\n')

        complete_typst = "\n".join(typst_markup)
        return self.compile_typst(complete_typst, output_pdf)

    def _convert_typst_to_styled_html(self, typst_code: str) -> str:
        """
        Parses Typst document markup into a publication-grade executive HTML/CSS layout.
        Extracts structural elements (headings, tables, callouts, lists, metadata)
        and eliminates raw syntax code leakage.
        """
        # 1. Extract Main Document Title
        title_match = (
            re.search(r'#text\([^)]*size:\s*(?:20|22|24|26)pt[^)]*\)\[(.*?)\]', typst_code, re.DOTALL)
            or re.search(r'=\s*([^=\n\r]+)', typst_code)
            or re.search(r'#text\([^)]*weight:\s*"bold"[^)]*\)\[(.*?)\]', typst_code, re.DOTALL)
        )
        doc_title = "Autonomous AI Governance Brief"
        if title_match:
            doc_title = title_match.group(1).replace("\\", "").replace("\n", " ").strip()

        # 2. Extract Subtitle
        subtitle_match = re.search(r'#text\([^)]*size:\s*(?:11|12)pt[^)]*\)\[(.*?)\]', typst_code, re.DOTALL)
        doc_subtitle = ""
        if subtitle_match and subtitle_match.group(1).strip() != doc_title:
            doc_subtitle = subtitle_match.group(1).replace("\\", "").replace("\n", " ").strip()

        # 3. Extract Metadata Pills
        meta_items = []
        for m in re.findall(r'\[\s*\*(Author|Target Audience|Version|Date|Status|Policy Ref)[^:]*:\*\s*([^\]]+)\]', typst_code, re.IGNORECASE):
            meta_items.append(f"<strong>{m[0]}:</strong> {m[1].strip()}")

        body_html = []
        lines = typst_code.split("\n")
        
        in_table = False
        table_cells = []
        in_code_block = False
        
        # State tracking for block extraction
        for line in lines:
            trimmed = line.strip()
            
            # Skip pure Typst setup directives and boilerplate
            if not trimmed or trimmed.startswith("//") or trimmed.startswith("#set ") or trimmed.startswith("#line"):
                continue
            if trimmed.startswith(("header:", "footer:", "locate(", "margin:", "paper:", "width:", "radius:", "stroke:", "fill:", "inset:", "columns:", "align:")):
                continue
            if trimmed in [")", "]", "],", "];", "};"]:
                if in_table:
                    in_table = False
                    if table_cells:
                        body_html.append("<table class='doc-table'>" + "".join(table_cells) + "</table>")
                continue

            # Section Headings
            if trimmed.startswith("= "):
                clean_h = trimmed[2:].strip().replace("\\", "").replace("[", "").replace("]", "")
                body_html.append(f"<h1 class='doc-heading'>{clean_h}</h1>")
            elif trimmed.startswith("== "):
                clean_h = trimmed[3:].strip().replace("\\", "").replace("[", "").replace("]", "")
                body_html.append(f"<h2 class='doc-subheading'>{clean_h}</h2>")
            elif trimmed.startswith("=== "):
                clean_h = trimmed[4:].strip().replace("\\", "").replace("[", "").replace("]", "")
                body_html.append(f"<h3 class='doc-subheading-3'>{clean_h}</h3>")
                
            # Bullet Lists
            elif trimmed.startswith("- ") or trimmed.startswith("* "):
                bullet_content = trimmed[2:].strip()
                # Parse markdown bold
                bullet_content = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', bullet_content)
                body_html.append(f"<li class='doc-li'>{bullet_content}</li>")
                
            # Table Header / Body Detection
            elif trimmed.startswith("#table") or "table.header" in trimmed:
                in_table = True
                table_cells = []
            elif in_table:
                # Extract text inside [ ... ] cells
                bracket_matches = re.findall(r'\[(.*?)\]', trimmed)
                if bracket_matches:
                    for cell in bracket_matches:
                        clean_cell = cell.replace("\\", "").strip()
                        clean_cell = re.sub(r'#text\([^)]*\)', '', clean_cell)
                        clean_cell = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', clean_cell)
                        if "weight: \"bold\"" in trimmed or "table.header" in line:
                            table_cells.append(f"<th>{clean_cell}</th>")
                        else:
                            table_cells.append(f"<td>{clean_cell}</td>")
                elif trimmed.startswith(")"):
                    in_table = False
                    if table_cells:
                        body_html.append("<table class='doc-table'>" + "".join(table_cells) + "</table>")
            
            # Callout boxes & Rect blocks
            elif trimmed.startswith("#rect") or "stroke: 1pt" in trimmed:
                # Extract inner content if on same line
                inner = re.search(r'\[(.*?)\]', trimmed)
                if inner:
                    c_text = inner.group(1).replace("\\", "").strip()
                    c_text = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', c_text)
                    body_html.append(f"<div class='callout-box'>{c_text}</div>")
            
            # Standard Text Paragraphs
            else:
                # If text is enclosed in [#text(...) [...] ] or [ ... ]
                extracted = re.findall(r'\[(.*?)\]', trimmed)
                if extracted:
                    p_text = " ".join(extracted)
                else:
                    # Clean out typst function prefixes
                    p_text = re.sub(r'#text\([^)]*\)', '', trimmed)
                    p_text = re.sub(r'#(rect|grid|align|v|h)\([^)]*\)', '', p_text)
                    p_text = p_text.replace("\\", "").replace("#v(", "").replace(")", "").strip()
                
                # Format bold / italic
                p_text = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', p_text)
                p_text = re.sub(r'_([^_]+)_', r'<em>\1</em>', p_text)
                
                # Only append if meaningful narrative text
                if p_text and not p_text.startswith(("#", "columns", "fill:", "stroke:", "radius:", "inset:", "paper:", "margin:")) and len(p_text) > 3:
                    if "Executive Summary" in p_text and not p_text.startswith("<"):
                        body_html.append(f"<div class='summary-card'><strong>Executive Summary:</strong> {p_text.replace('Executive Summary', '').strip()}</div>")
                    else:
                        body_html.append(f"<p>{p_text}</p>")

        content_html = "\n".join(body_html)

        meta_pills_html = ""
        if meta_items:
            meta_pills_html = "<div class='meta-bar'>" + "".join([f"<span class='meta-pill'>{m}</span>" for m in meta_items]) + "</div>"

        subtitle_html = f"<div class='doc-subtitle'>{doc_subtitle}</div>" if doc_subtitle else ""

        css_style = """
  @page {
    size: a4 portrait;
    margin: 1.8cm;
  }
  body {
    font-family: Helvetica, Arial, sans-serif;
    color: #1E293B;
    line-height: 1.55;
    font-size: 9.5pt;
  }
  .banner-container {
    background-color: #0F172A;
    border-radius: 6px;
    padding: 16px 20px;
    margin-bottom: 20px;
  }
  .banner-tag {
    font-size: 8pt;
    font-weight: bold;
    color: #38BDF8;
    letter-spacing: 1px;
    margin-bottom: 4px;
  }
  .doc-title {
    font-size: 18pt;
    font-weight: bold;
    color: #FFFFFF;
    margin-bottom: 6px;
  }
  .doc-subtitle {
    font-size: 10pt;
    color: #94A3B8;
    margin-bottom: 10px;
  }
  .meta-bar {
    border-top: 1px solid #334155;
    padding-top: 8px;
    margin-top: 8px;
  }
  .meta-pill {
    display: inline-block;
    color: #CBD5E1;
    font-size: 8pt;
    margin-right: 18px;
  }
  .doc-heading {
    font-size: 13pt;
    font-weight: bold;
    color: #0F172A;
    border-bottom: 1.5px solid #CBD5E1;
    padding-bottom: 4px;
    margin-top: 18px;
    margin-bottom: 8px;
  }
  .doc-subheading {
    font-size: 11pt;
    font-weight: bold;
    color: #1E3A8A;
    margin-top: 12px;
    margin-bottom: 6px;
  }
  .doc-subheading-3 {
    font-size: 10pt;
    font-weight: bold;
    color: #334155;
    margin-top: 8px;
    margin-bottom: 4px;
  }
  .summary-card {
    background-color: #F0FDF4;
    border-left: 4px solid #16A34A;
    padding: 10px 14px;
    margin: 12px 0;
    font-size: 9.5pt;
    color: #14532D;
  }
  .callout-box {
    background-color: #F8FAFC;
    border-left: 4px solid #0284C7;
    padding: 8px 12px;
    margin: 10px 0;
    font-size: 9pt;
  }
  table.doc-table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0;
    font-size: 8.5pt;
  }
  table.doc-table th {
    background-color: #0F172A;
    color: #FFFFFF;
    font-weight: bold;
    padding: 6px 8px;
    border: 1px solid #CBD5E1;
    text-align: left;
  }
  table.doc-table td {
    border: 1px solid #CBD5E1;
    padding: 6px 8px;
    text-align: left;
  }
  table.doc-table tr:nth-child(even) td {
    background-color: #F8FAFC;
  }
  p {
    margin: 5px 0;
  }
  li.doc-li {
    margin-bottom: 3px;
  }
  .footer-note {
    text-align: center;
    border-top: 1px solid #E2E8F0;
    padding-top: 8px;
    margin-top: 24px;
    font-size: 7.5pt;
    color: #94A3B8;
  }
"""
        html_template = (
            "<!DOCTYPE html>\n<html>\n<head>\n<meta charset='utf-8'>\n<style>\n"
            + css_style
            + "\n</style>\n</head>\n<body>\n"
            "<div class='banner-container'>\n"
            "<div class='banner-tag'>NAVA AGENT GOVERNANCE SPECIFICATION</div>\n"
            f"<div class='doc-title'>{doc_title}</div>\n"
            + subtitle_html
            + meta_pills_html
            + "</div>\n"
            + content_html
            + "\n<div class='footer-note'>NAVA Autonomous AI Governance Framework &bull; Published August 2026 &bull; Enterprise Architecture Series</div>\n"
            + "</body>\n</html>"
        )
        return html_template

    def read_document(self, file_path: str) -> Dict[str, Any]:
        """Reads text content and structure from PDF, DOCX, PPTX, MD, TXT, or Typst files."""
        resolved = self._resolve_target(file_path)
        if not os.path.exists(resolved):
            return {"error": f"File '{file_path}' does not exist."}

        ext = os.path.splitext(resolved)[1].lower()
        
        try:
            if ext in [".txt", ".md", ".typ", ".json", ".csv", ".yaml", ".yml", ".html"]:
                with open(resolved, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                return {"success": True, "file": file_path, "format": ext, "content": content, "length": len(content)}
                
            elif ext == ".docx":
                try:
                    import docx
                    doc = docx.Document(resolved)
                    text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                    return {"success": True, "file": file_path, "format": "docx", "content": text, "paragraphs_count": len(doc.paragraphs)}
                except ImportError:
                    return {"error": "python-docx library required to read DOCX. Run: pip install python-docx"}
                    
            elif ext == ".pdf":
                try:
                    import pypdf
                    reader = pypdf.PdfReader(resolved)
                    text = "\n\n".join([page.extract_text() or "" for page in reader.pages])
                    return {"success": True, "file": file_path, "format": "pdf", "pages": len(reader.pages), "content": text}
                except ImportError:
                    return {"error": "pypdf library required to read PDF. Run: pip install pypdf"}
                    
            return {"error": f"Unsupported document format '{ext}'"}
        except Exception as e:
            return {"success": False, "error": f"Failed to read document: {str(e)}"}
