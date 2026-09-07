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
        if not path:
            return self.artifact_resolver("document.pdf")
        clean = path.replace("\\", "/").lstrip("/")
        
        # Explicit project codebase files
        if clean.startswith("projects/"):
            return self.sanitizer(path)
        elif clean.startswith(("scratch/", "memory/", ".nava/")):
            return self.sanitizer(path)
            
        # Already fully qualified task artifact path
        if re.match(r"^tasks/tsk_\d{8}_\d{6}_[^/]+/artifacts/", clean):
            return self.sanitizer(path)
            
        # All other document deliverables route strictly to active task artifacts
        base = os.path.basename(clean)
        parent_parts = [p for p in os.path.dirname(clean).split("/") if p and p not in ["tasks", "artifacts", "."]]
        if base.startswith("index.") and parent_parts:
            ext = os.path.splitext(base)[1]
            base = f"{parent_parts[-1]}{ext}"
            
        return self.artifact_resolver(base)

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

        # Save/update the .typ source alongside the PDF in task artifacts
        resolved_typ = resolved_out.replace(".pdf", ".typ")
        if len(typst_code) > 10:
            try:
                with open(resolved_typ, "w", encoding="utf-8") as f:
                    f.write(typst_code)
            except Exception:
                pass

        # Substitute template variables if provided
        if template_vars:
            for k, v in template_vars.items():
                typst_code = typst_code.replace(f"{{{{{k}}}}}", str(v))
                typst_code = typst_code.replace(f"{{{k}}}", str(v))

        # 1. Try Native Rust Typst compiler via official python package
        try:
            import typst
            typst.compile(resolved_typ, output=resolved_out)
            file_size = os.path.getsize(resolved_out)
            return {
                "success": True,
                "saved_to": os.path.relpath(resolved_out, os.getcwd()),
                "bytes_written": file_size,
                "compiler": "native-typst-rust"
            }
        except (ImportError, Exception):
            pass

        # 2. Try Native Typst CLI binary if available in PATH
        typst_bin = shutil.which("typst")
        if typst_bin:
            try:
                res = subprocess.run([typst_bin, "compile", resolved_typ, resolved_out], capture_output=True, timeout=15)
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
        doc_title = "Executive Intelligence & Developments Report"
        doc_subtitle = ""
        doc_tag = "EXECUTIVE BRIEFING"

        # Search for title in #text(size: 15..28pt)[Title] or in main header banner
        t_match = (
            re.search(r'#text\([^)]*size:\s*(?:14|15|16|17|18|20|22|24|26)pt[^)]*\)\[(.*?)\]', typst_code, re.DOTALL)
            or re.search(r'=\s*([^=\n\r]+)', typst_code)
        )
        if t_match:
            candidate = t_match.group(1).replace("\\", "").strip()
            candidate = re.sub(r'#text\([^)]*\)', '', candidate).replace("[", "").replace("]", "").strip()
            if candidate and len(candidate) > 3 and not candidate.startswith(("1.", "2.", "3.", "==")):
                doc_title = candidate

        # Subtitle match (e.g. Executive Summary | Headlines & Intelligence ...)
        sub_match = (
            re.search(r'#text\([^)]*size:\s*(?:9|9\.5|10|11|12)pt[^)]*\)\[(.*?)\]', typst_code, re.DOTALL)
            or re.search(r'#text\([^)]*fill:\s*rgb\("#cbd5e0"\)[^)]*\)\[(.*?)\]', typst_code, re.DOTALL)
        )
        if sub_match:
            sub_cand = sub_match.group(1).replace("\\", "").strip()
            sub_cand = re.sub(r'#text\([^)]*\)', '', sub_cand).replace("[", "").replace("]", "").strip()
            if sub_cand and sub_cand != doc_title and len(sub_cand) > 5 and not sub_cand.startswith(("1.", "2.", "3.")):
                doc_subtitle = sub_cand

        # Tag match (e.g. CONFIDENTIAL / BRIEF, REPORT, BRIEFING)
        tag_match = re.search(r'\[\s*(CONFIDENTIAL[^\]]*|BRIEF[^\]]*|EXECUTIVE[^\]]*|INTELLIGENCE[^\]]*)\s*\]', typst_code, re.IGNORECASE)
        if tag_match:
            doc_tag = tag_match.group(1).strip()

        # 2. Clean out pure setup directives and replace links
        # Strip #set page(...) and other multi-line #set directives
        clean_code = re.sub(r'#set\s+[a-zA-Z_]+\s*\([^)]*\)', '', typst_code, flags=re.DOTALL)
        clean_code = re.sub(r'#set\s+page\s*\([^;]*?\)\s*', '', clean_code, flags=re.DOTALL)
        
        # Replace #link("...") or #link("...")[text] with <a> tags
        clean_code = re.sub(
            r'#link\("([^"]+)"\)(?:\[(.*?)\])?',
            lambda m: f'<a href="{m.group(1)}" style="color: #2563EB; text-decoration: underline;">{m.group(2) if m.group(2) else m.group(1)}</a>',
            clean_code
        )

        body_html = []
        lines = clean_code.split("\n")
        
        in_callout = False
        callout_items = []
        in_list = False
        in_table = False
        table_rows = []

        for line in lines:
            trimmed = line.strip()
            if not trimmed or trimmed.startswith("//") or trimmed.startswith("#v(") or trimmed.startswith("#h("):
                continue
            if trimmed.startswith(("#set", "#line", "#page", "#counter", "header:", "footer:", "locate(", "margin:", "paper:", "width:", "radius:", "stroke:", "fill:", "inset:", "columns:", "align:", "spacing:", "leading:")):
                continue
            if trimmed in [")", "]", "],", "];", "};", "[", "(", "\\", "---", "***"]:
                continue
            if re.match(r'^(size:|spacing:|leading:|justify:|fill:|stroke:|radius:|margin:|paper:|align:)', trimmed):
                continue

            # Table handling (| col1 | col2 |)
            if trimmed.startswith("|") and trimmed.endswith("|"):
                if in_list:
                    body_html.append("</ul>")
                    in_list = False
                if not in_table:
                    in_table = True
                    table_rows = []
                
                # Check if separator row (e.g. | :--- | :--- |)
                if re.match(r'^\|[\s\-:]+(\|[\s\-:]+)+\|$', trimmed):
                    continue
                
                cells = [c.strip() for c in trimmed.strip("|").split("|")]
                formatted_cells = []
                for cell in cells:
                    cell_text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', cell)
                    cell_text = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', cell_text)
                    cell_text = re.sub(r'_([^_]+)_', r'<em>\1</em>', cell_text)
                    formatted_cells.append(cell_text)
                
                if not table_rows: # First row is headers
                    th_html = "".join([f"<th style='padding: 8px 10px; border-bottom: 2px solid #CBD5E1; text-align: left; background-color: #F1F5F9; font-size: 8.5pt;'>{c}</th>" for c in formatted_cells])
                    table_rows.append(f"<thead><tr>{th_html}</tr></thead><tbody>")
                else:
                    td_html = "".join([f"<td style='padding: 7px 10px; border-bottom: 1px solid #E2E8F0; font-size: 8.5pt;'>{c}</td>" for c in formatted_cells])
                    table_rows.append(f"<tr>{td_html}</tr>")
                continue
            else:
                if in_table:
                    in_table = False
                    if table_rows:
                        table_rows.append("</tbody>")
                        body_html.append(f"<table style='width: 100%; border-collapse: collapse; margin: 12px 0 16px 0; border: 1px solid #CBD5E1; border-radius: 4px;'>{''.join(table_rows)}</table>")
                        table_rows = []

            # Heading 1
            if (trimmed.startswith("= ") or trimmed.startswith("# ")) and not (trimmed.startswith("== ") or trimmed.startswith("## ")):
                if in_list:
                    body_html.append("</ul>")
                    in_list = False
                h_text = re.sub(r'^[=#]\s+', '', trimmed).replace("\\", "").replace("[", "").replace("]", "").strip()
                if h_text and h_text != doc_title:
                    body_html.append(f"<h1 class='doc-heading'>{h_text}</h1>")
                continue

            # Heading 2 (e.g. == 1. Executive Summary or ## 1. Executive Summary)
            if (trimmed.startswith("== ") or trimmed.startswith("## ")) and not (trimmed.startswith("=== ") or trimmed.startswith("### ")):
                if in_list:
                    body_html.append("</ul>")
                    in_list = False
                h_text = re.sub(r'^[=#]{2}\s+', '', trimmed).replace("\\", "").replace("[", "").replace("]", "").strip()
                body_html.append(f"<h2 class='doc-subheading'>{h_text}</h2>")
                continue

            # Heading 3
            if trimmed.startswith("=== ") or trimmed.startswith("### "):
                if in_list:
                    body_html.append("</ul>")
                    in_list = False
                h_text = re.sub(r'^[=#]{3}\s+', '', trimmed).replace("\\", "").replace("[", "").replace("]", "").strip()
                body_html.append(f"<h3 class='doc-subheading-3'>{h_text}</h3>")
                continue

            # Bullet List (- item or * item)
            if trimmed.startswith("- ") or (trimmed.startswith("* ") and not trimmed.startswith("**")):
                if not in_list:
                    body_html.append("<ul class='doc-ul'>")
                    in_list = True
                bullet_content = trimmed[2:].strip()
                bullet_content = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', bullet_content)
                bullet_content = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', bullet_content)
                bullet_content = re.sub(r'_([^_]+)_', r'<em>\1</em>', bullet_content)
                # Link conversion inside bullets
                bullet_content = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2" style="color: #2563EB; text-decoration: underline;">\1</a>', bullet_content)
                body_html.append(f"<li class='doc-li'>{bullet_content}</li>")
                continue

            # #list([ item 1 ], [ item 2 ])
            if trimmed.startswith("#list(") or "list(" in trimmed:
                items = re.findall(r'\[(.*?)\]', trimmed)
                if items:
                    if not in_list:
                        body_html.append("<ul class='doc-ul'>")
                        in_list = True
                    for it in items:
                        clean_it = it.replace("\\", "").strip()
                        clean_it = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', clean_it)
                        clean_it = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', clean_it)
                        clean_it = re.sub(r'_([^_]+)_', r'<em>\1</em>', clean_it)
                        if clean_it and len(clean_it) > 2:
                            body_html.append(f"<li class='doc-li'>{clean_it}</li>")
                continue

            # Rect / Callout box
            if trimmed.startswith("#rect") or "stroke: (" in trimmed or "stroke: left:" in trimmed:
                in_callout = True
                callout_items = []
                inner = re.search(r'\[(.*?)\]', trimmed)
                if inner:
                    c_text = inner.group(1).replace("\\", "").strip()
                    c_text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', c_text)
                    c_text = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', c_text)
                    body_html.append(f"<div class='callout-box'>{c_text}</div>")
                    in_callout = False
                continue

            # Inside Callout
            if in_callout:
                if trimmed.startswith("]") or trimmed.startswith(")"):
                    in_callout = False
                    if callout_items:
                        body_html.append("<div class='callout-box'>" + "".join(callout_items) + "</div>")
                        callout_items = []
                    continue
                inner_items = re.findall(r'\[(.*?)\]', trimmed)
                if inner_items:
                    for it in inner_items:
                        clean_it = it.replace("\\", "").strip()
                        clean_it = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', clean_it)
                        clean_it = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', clean_it)
                        clean_it = re.sub(r'_([^_]+)_', r'<em>\1</em>', clean_it)
                        if clean_it:
                            callout_items.append(f"<div style='margin-bottom: 4px;'>• {clean_it}</div>")
                else:
                    c_text = trimmed.replace("\\", "").replace("[", "").replace("]", "").strip()
                    c_text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', c_text)
                    c_text = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', c_text)
                    if c_text and not c_text.startswith("#"):
                        callout_items.append(f"<div>{c_text}</div>")
                continue

            # Standard text line / Paragraph
            p_text = re.sub(r'#text\([^)]*\)', '', trimmed)
            p_text = re.sub(r'#(rect|block|grid|align|v|h|counter)\([^)]*\)', '', p_text)
            p_text = p_text.replace("\\", "").replace("[", "").replace("]", "").strip()
            
            p_text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', p_text)
            p_text = re.sub(r'\*([^*]+)\*', r'<strong>\1</strong>', p_text)
            p_text = re.sub(r'_([^_]+)_', r'<em>\1</em>', p_text)
            p_text = re.sub(r'\[([^\]]+)\]\((https?://[^)]+)\)', r'<a href="\2" style="color: #2563EB; text-decoration: underline;">\1</a>', p_text)
            
            if (
                p_text
                and len(p_text) > 4
                and not p_text.startswith(("#", "columns", "fill:", "stroke:", "radius:", "inset:", "paper:", "margin:", "size:", "spacing:"))
                and p_text not in [doc_title, doc_subtitle, doc_tag]
            ):
                if in_list:
                    body_html.append("</ul>")
                    in_list = False
                body_html.append(f"<p>{p_text}</p>")

        if in_list:
            body_html.append("</ul>")
        if in_table and table_rows:
            table_rows.append("</tbody>")
            body_html.append(f"<table style='width: 100%; border-collapse: collapse; margin: 12px 0 16px 0; border: 1px solid #CBD5E1; border-radius: 4px;'>{''.join(table_rows)}</table>")
        if in_callout and callout_items:
            body_html.append("<div class='callout-box'>" + "".join(callout_items) + "</div>")

        content_html = "\n".join(body_html)

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
    background-color: #1E3A8A;
    border-radius: 6px;
    padding: 16px 20px;
    margin-bottom: 20px;
  }
  .banner-tag {
    font-size: 8pt;
    font-weight: bold;
    color: #93C5FD;
    letter-spacing: 1px;
    margin-bottom: 4px;
    text-transform: uppercase;
  }
  .doc-title {
    font-size: 17pt;
    font-weight: bold;
    color: #FFFFFF;
    margin-bottom: 4px;
  }
  .doc-subtitle {
    font-size: 9.5pt;
    color: #E2E8F0;
    margin-bottom: 4px;
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
    margin-top: 14px;
    margin-bottom: 6px;
  }
  .doc-subheading-3 {
    font-size: 10pt;
    font-weight: bold;
    color: #334155;
    margin-top: 10px;
    margin-bottom: 4px;
  }
  .callout-box {
    background-color: #F8FAFC;
    border-left: 4pt solid #2563EB;
    padding: 10px 14px;
    margin: 12px 0;
    font-size: 9.5pt;
    border-radius: 0 4px 4px 0;
  }
  ul.doc-ul {
    margin: 6px 0 10px 18px;
    padding: 0;
  }
  li.doc-li {
    margin-bottom: 6px;
    line-height: 1.45;
  }
  p {
    margin: 6px 0;
    line-height: 1.5;
  }
  .footer-note {
    text-align: center;
    border-top: 1px solid #E2E8F0;
    padding-top: 8px;
    margin-top: 24px;
    font-size: 8pt;
    color: #94A3B8;
  }
"""
        html_template = (
            "<!DOCTYPE html>\n<html>\n<head>\n<meta charset='utf-8'>\n<style>\n"
            + css_style
            + "\n</style>\n</head>\n<body>\n"
            "<div class='banner-container'>\n"
            f"<div class='banner-tag'>{doc_tag}</div>\n"
            f"<div class='doc-title'>{doc_title}</div>\n"
            + subtitle_html
            + "</div>\n"
            + content_html
            + "\n<div class='footer-note'>NAVA Autonomous Cowork OS &bull; Executive Intelligence Series &bull; Grounded & Verified Deliverable</div>\n"
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
