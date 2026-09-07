"""
presentation_engine.py — Dedicated Gamma-Style Presentation, Slidev & Multi-Format Slide Engine.
Provides dynamic theme palettes, rich layout variations (Bento, Timeline, Split, Hero, Metrics),
Slidev Markdown authoring, standalone interactive HTML5 deck rendering, and modernized PPTX export.
"""
import os
import re
import json
import shutil
import subprocess
from typing import Dict, Any, List, Optional, Callable


class PresentationEngine:
    """
    Core engine for generating Gamma-grade presentations with bespoke dynamic designs,
    topic-aware color palettes, multi-column bento grids, timelines, and multi-tier export.
    """

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
            return self.artifact_resolver("presentation.html")
        clean = path.replace("\\", "/").lstrip("/")
        
        # Explicit project codebase files
        if clean.startswith("projects/"):
            return self.sanitizer(path)
        elif clean.startswith(("scratch/", "memory/", ".nava/")):
            return self.sanitizer(path)
            
        # Already fully qualified task artifact path
        if re.match(r"^tasks/tsk_\d{8}_\d{6}_[^/]+/artifacts/", clean):
            return self.sanitizer(path)
            
        # All other presentation deliverables route strictly to active task artifacts
        base = os.path.basename(clean)
        # If generic "index.html" was used with a folder like "agentic_ai_presentation/index.html", use folder as prefix
        parent_parts = [p for p in os.path.dirname(clean).split("/") if p and p not in ["tasks", "artifacts", "."]]
        if base.startswith("index.") and parent_parts:
            ext = os.path.splitext(base)[1]
            base = f"{parent_parts[-1]}{ext}"
            
        return self.artifact_resolver(base)

    # =========================================================================
    # Theme & Palette Resolver
    # =========================================================================

    def _resolve_palette(self, theme_name: str, custom_theme: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Resolves dynamic color palettes based on topic, theme name, or custom overrides."""
        t_key = (theme_name or "").lower().replace("-", "_")

        palettes = {
            "cyber_neon": {
                "bg_main": "#06090E",
                "slide_bg": "#0B1017",
                "card_bg": "rgba(15, 23, 42, 0.8)",
                "card_border": "rgba(6, 182, 212, 0.3)",
                "accent": "#06B6D4",
                "accent_secondary": "#10B981",
                "gradient": "from-cyan-400 via-teal-300 to-emerald-400",
                "tag_bg": "bg-cyan-500/15 border-cyan-500/30 text-cyan-300",
                "text_primary": "#F8FAFC",
                "text_secondary": "#94A3B8"
            },
            "emerald_finance": {
                "bg_main": "#02120D",
                "slide_bg": "#052218",
                "card_bg": "rgba(6, 44, 34, 0.75)",
                "card_border": "rgba(16, 185, 129, 0.3)",
                "accent": "#10B981",
                "accent_secondary": "#34D399",
                "gradient": "from-emerald-400 via-teal-300 to-cyan-400",
                "tag_bg": "bg-emerald-500/15 border-emerald-500/30 text-emerald-300",
                "text_primary": "#F8FAFC",
                "text_secondary": "#A7F3D0"
            },
            "purple_modern": {
                "bg_main": "#090714",
                "slide_bg": "#100D22",
                "card_bg": "rgba(26, 18, 51, 0.8)",
                "card_border": "rgba(139, 92, 246, 0.3)",
                "accent": "#8B5CF6",
                "accent_secondary": "#EC4899",
                "gradient": "from-violet-400 via-purple-300 to-fuchsia-400",
                "tag_bg": "bg-purple-500/15 border-purple-500/30 text-purple-300",
                "text_primary": "#FDF4FF",
                "text_secondary": "#DDD6FE"
            },
            "sunset_warm": {
                "bg_main": "#120704",
                "slide_bg": "#1E0D08",
                "card_bg": "rgba(46, 20, 14, 0.8)",
                "card_border": "rgba(245, 158, 11, 0.3)",
                "accent": "#F59E0B",
                "accent_secondary": "#F43F5E",
                "gradient": "from-amber-400 via-orange-400 to-rose-400",
                "tag_bg": "bg-amber-500/15 border-amber-500/30 text-amber-300",
                "text_primary": "#FFFBEB",
                "text_secondary": "#FED7AA"
            },
            "dark_executive": {
                "bg_main": "#080D1A",
                "slide_bg": "#0F172A",
                "card_bg": "rgba(30, 41, 59, 0.8)",
                "card_border": "rgba(56, 189, 248, 0.25)",
                "accent": "#38BDF8",
                "accent_secondary": "#3B82F6",
                "gradient": "from-cyan-400 via-sky-400 to-indigo-400",
                "tag_bg": "bg-sky-500/15 border-sky-500/30 text-sky-300",
                "text_primary": "#F8FAFC",
                "text_secondary": "#94A3B8"
            },
            "minimal_light": {
                "bg_main": "#F1F5F9",
                "slide_bg": "#FFFFFF",
                "card_bg": "#F8FAFC",
                "card_border": "#E2E8F0",
                "accent": "#0284C7",
                "accent_secondary": "#475569",
                "gradient": "from-slate-900 via-slate-800 to-sky-800",
                "tag_bg": "bg-slate-200 border-slate-300 text-slate-800",
                "text_primary": "#0F172A",
                "text_secondary": "#475569"
            }
        }

        # Select base palette
        base = palettes.get(t_key, palettes["dark_executive"]).copy()

        # Apply custom overrides if provided
        if custom_theme and isinstance(custom_theme, dict):
            if "primaryColor" in custom_theme or "primary_color" in custom_theme:
                base["accent"] = custom_theme.get("primaryColor") or custom_theme.get("primary_color")
            if "accentColor" in custom_theme or "accent_color" in custom_theme:
                base["accent_secondary"] = custom_theme.get("accentColor") or custom_theme.get("accent_color")
            if "backgroundColor" in custom_theme or "bg_color" in custom_theme:
                base["slide_bg"] = custom_theme.get("backgroundColor") or custom_theme.get("bg_color")
                base["bg_main"] = base["slide_bg"]

        return base

    # =========================================================================
    # 1. Slidev Markdown Compilation & Multi-Tier Export Pipeline
    # =========================================================================

    def compile_slidev(
        self,
        source: str,
        output_path: str,
        format_type: Optional[str] = None,
        theme: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Compiles Slidev Markdown into target output format (.pptx, .pdf, or .html).
        Uses @slidev/cli if Node is available, with built-in high-fidelity HTML/PPTX
        renderers as reliable zero-dependency fallbacks.
        """
        resolved_out = self._resolve_target(output_path)
        os.makedirs(os.path.dirname(os.path.abspath(resolved_out)), exist_ok=True)

        ext = os.path.splitext(resolved_out)[1].lower()
        target_format = (format_type or ext.lstrip(".") or "html").lower()

        # Read source markdown
        slidev_md = source
        if os.path.exists(source):
            with open(source, "r", encoding="utf-8", errors="replace") as f:
                slidev_md = f.read()
        elif len(source) < 300 and (source.endswith(".md") or "/" in source or "\\" in source):
            resolved_src = self._resolve_target(source)
            if os.path.exists(resolved_src):
                with open(resolved_src, "r", encoding="utf-8", errors="replace") as f:
                    slidev_md = f.read()

        resolved_md = os.path.splitext(resolved_out)[0] + ".md"
        try:
            with open(resolved_md, "w", encoding="utf-8") as f:
                f.write(slidev_md)
        except Exception:
            pass

        # 1. Tier 1: Try Native Slidev CLI via npx / Node
        npx_bin = shutil.which("npx") or shutil.which("slidev")
        if npx_bin:
            try:
                cmd = ["npx", "@slidev/cli", "export", resolved_md, "--format", target_format, "--output", resolved_out]
                if theme:
                    cmd.extend(["--theme", theme])
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if proc.returncode == 0 and os.path.exists(resolved_out) and os.path.getsize(resolved_out) > 0:
                    return {
                        "success": True,
                        "saved_to": os.path.relpath(resolved_out, os.getcwd()),
                        "format": target_format,
                        "source_markdown": os.path.relpath(resolved_md, os.getcwd()),
                        "compiler": "slidev-cli-native",
                        "bytes_written": os.path.getsize(resolved_out)
                    }
            except Exception:
                pass

        # 2. Tier 2: Built-in Standalone High-Fidelity HTML Presentation Deck
        slides_data = self._parse_slidev_to_slides(slidev_md)
        html_content = self.generate_standalone_html(
            title=slides_data.get("title", "Executive Presentation"),
            slides=slides_data.get("slides", []),
            theme_name=theme or "cyber_neon"
        )

        if target_format in ["html", "htm"]:
            with open(resolved_out, "w", encoding="utf-8") as f:
                f.write(html_content)
            return {
                "success": True,
                "saved_to": os.path.relpath(resolved_out, os.getcwd()),
                "format": "html",
                "source_markdown": os.path.relpath(resolved_md, os.getcwd()),
                "compiler": "nava-dynamic-slide-engine",
                "bytes_written": os.path.getsize(resolved_out)
            }
        elif target_format in ["pptx", "ppt"]:
            self._generate_modern_pptx(
                filename=resolved_out,
                title=slides_data.get("title", "Executive Presentation"),
                slides=slides_data.get("slides", []),
                theme_name=theme or "cyber_neon"
            )
            return {
                "success": True,
                "saved_to": os.path.relpath(resolved_out, os.getcwd()),
                "format": "pptx",
                "source_markdown": os.path.relpath(resolved_md, os.getcwd()),
                "compiler": "nava-modern-pptx-engine",
                "bytes_written": os.path.getsize(resolved_out) if os.path.exists(resolved_out) else 0
            }
        else:
            html_out = resolved_out.replace(".pdf", ".html")
            with open(html_out, "w", encoding="utf-8") as f:
                f.write(html_content)
            return {
                "success": True,
                "saved_to": os.path.relpath(html_out, os.getcwd()),
                "format": "html",
                "source_markdown": os.path.relpath(resolved_md, os.getcwd()),
                "compiler": "nava-dynamic-slide-engine",
                "bytes_written": os.path.getsize(html_out)
            }

    # =========================================================================
    # 2. Dynamic Template & Presentation Rendering
    # =========================================================================

    def render_template(
        self,
        template_name: str,
        title: str,
        slides: List[Dict[str, Any]],
        output_path: str,
        author: str = "NAVA Engineering Intelligence",
        theme: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Renders a completely bespoke, dynamic presentation deck with no hardcoded boilerplate.
        Outputs Slidev Markdown source, interactive HTML presentation, AND companion PPTX.
        """
        t_name = template_name or "dark_executive"
        resolved_out = self._resolve_target(output_path)
        os.makedirs(os.path.dirname(os.path.abspath(resolved_out)), exist_ok=True)

        # 1. Convert structured slides into Slidev Markdown
        slidev_md = self._build_slidev_markdown(
            title=title,
            slides=slides,
            author=author,
            template_name=t_name,
            custom_theme=theme
        )

        # 2. Save .md artifact
        resolved_md = os.path.splitext(resolved_out)[0] + ".md"
        with open(resolved_md, "w", encoding="utf-8") as f:
            f.write(slidev_md)

        ext = os.path.splitext(resolved_out)[1].lower()
        if ext in [".pptx", ".ppt"]:
            self._generate_modern_pptx(
                filename=resolved_out,
                title=title,
                slides=slides,
                theme_name=t_name,
                custom_theme=theme
            )
            # Companion HTML deck
            companion_html = resolved_out.replace(ext, ".html")
            html_deck = self.generate_standalone_html(title, slides, t_name, author, theme)
            with open(companion_html, "w", encoding="utf-8") as f:
                f.write(html_deck)
        else:
            # Default to interactive HTML deck
            html_deck = self.generate_standalone_html(title, slides, t_name, author, theme)
            with open(resolved_out, "w", encoding="utf-8") as f:
                f.write(html_deck)
            # Companion PPTX
            companion_pptx = os.path.splitext(resolved_out)[0] + ".pptx"
            try:
                self._generate_modern_pptx(
                    filename=companion_pptx,
                    title=title,
                    slides=slides,
                    theme_name=t_name,
                    custom_theme=theme
                )
            except Exception:
                pass

        file_size = os.path.getsize(resolved_out) if os.path.exists(resolved_out) else 0
        return {
            "success": True,
            "saved_to": os.path.relpath(resolved_out, os.getcwd()),
            "source_markdown": os.path.relpath(resolved_md, os.getcwd()),
            "template": t_name,
            "total_slides": len(slides),
            "bytes_written": file_size
        }

    # =========================================================================
    # Helpers: Column and Card Formatters
    # =========================================================================

    def _extract_column(self, slide_dict: Dict[str, Any], side: str) -> Any:
        """Extracts column content from flexible dictionary keys."""
        if side == "left":
            return (
                slide_dict.get("column_left")
                or slide_dict.get("col_left")
                or slide_dict.get("left_col")
                or slide_dict.get("column_1")
                or slide_dict.get("col_1")
                or slide_dict.get("left_column")
                or slide_dict.get("left_content")
                or slide_dict.get("left")
                or ""
            )
        else:
            return (
                slide_dict.get("column_right")
                or slide_dict.get("col_right")
                or slide_dict.get("right_col")
                or slide_dict.get("column_2")
                or slide_dict.get("col_2")
                or slide_dict.get("right_column")
                or slide_dict.get("right_content")
                or slide_dict.get("right")
                or ""
            )

    def _format_column_html(self, col_data: Any, palette: Dict[str, str], is_left: bool = True) -> str:
        """Formats column dictionary or string to clean HTML with custom palette colors."""
        if not col_data:
            return ""
        if isinstance(col_data, str):
            return f"<p class='text-xs text-slate-300 leading-relaxed'>{col_data}</p>"
        if isinstance(col_data, dict):
            parts = []
            c_title = col_data.get("title") or col_data.get("header") or col_data.get("name") or ""
            c_subtitle = col_data.get("subtitle") or col_data.get("tag") or ""
            
            sub_color = "text-rose-400" if is_left and "legacy" in c_title.lower() or "traditional" in c_title.lower() else "text-cyan-400"
            bullet_color = "text-rose-400" if is_left and "legacy" in c_title.lower() or "traditional" in c_title.lower() else "text-cyan-400"

            if c_title:
                parts.append(f"<h3 class='text-lg font-bold text-slate-100 mb-1'>{c_title}</h3>")
            if c_subtitle:
                parts.append(f"<div class='text-xs {sub_color} font-semibold mb-3 tracking-wide'>{c_subtitle}</div>")

            points = col_data.get("points") or col_data.get("bullets") or col_data.get("items") or []
            if isinstance(points, list) and points:
                items_html = "".join([
                    f"<li class='flex items-start gap-2 text-xs text-slate-300 mb-2'><span class='{bullet_color} font-bold'>&bull;</span><span class='leading-relaxed'>{p}</span></li>"
                    for p in points
                ])
                parts.append(f"<ul class='space-y-1 my-2'>{items_html}</ul>")
            elif col_data.get("content") or col_data.get("description"):
                body_txt = col_data.get("content") or col_data.get("description")
                parts.append(f"<p class='text-xs text-slate-300 leading-relaxed'>{body_txt}</p>")
            return "".join(parts)
        return str(col_data)

    def _format_column_md(self, col_data: Any) -> str:
        """Formats column dictionary or string to clean Slidev Markdown."""
        if not col_data:
            return ""
        if isinstance(col_data, str):
            return col_data
        if isinstance(col_data, dict):
            parts = []
            c_title = col_data.get("title") or col_data.get("header") or col_data.get("name") or ""
            c_subtitle = col_data.get("subtitle") or col_data.get("tag") or ""
            if c_title:
                parts.append(f"### {c_title}")
            if c_subtitle:
                parts.append(f"<p class='text-xs text-cyan-400 font-semibold mb-2'>{c_subtitle}</p>")
            points = col_data.get("points") or col_data.get("bullets") or col_data.get("items") or []
            if isinstance(points, list):
                for p in points:
                    parts.append(f"- {p}")
            elif col_data.get("content") or col_data.get("description"):
                parts.append(str(col_data.get("content") or col_data.get("description")))
            return "\n".join(parts)
        return str(col_data)

    # =========================================================================
    # 3. Slidev Markdown Builder
    # =========================================================================

    def _build_slidev_markdown(
        self,
        title: str,
        slides: List[Dict[str, Any]],
        author: str,
        template_name: str,
        custom_theme: Optional[Dict[str, Any]] = None
    ) -> str:
        """Constructs full Slidev Markdown with dynamic layout components."""
        palette = self._resolve_palette(template_name, custom_theme)
        bg_color = palette["slide_bg"]
        text_color = "text-white" if "#" in bg_color and bg_color.lower() not in ["#ffffff", "#fafafa", "#f8fafc"] else "text-slate-900"
        card_bg = "bg-slate-800/80 border border-slate-700/80 shadow-xl"
        card_text = "text-slate-300"

        md_parts = [
            "---",
            "theme: default",
            f"background: '{bg_color}'",
            f"class: '{text_color} p-12'",
            "highlighter: shiki",
            "drawings:",
            "  persist: false",
            "transition: slide-left",
            f"title: '{title}'",
            "---",
            ""
        ]

        for idx, s in enumerate(slides):
            if idx > 0:
                md_parts.append("---")
                md_parts.append(f"background: '{bg_color}'")
                md_parts.append(f"class: '{text_color} p-10'")
                md_parts.append("---")
                md_parts.append("")

            s_title = s.get("title", f"Slide {idx + 1}")
            s_subtitle = s.get("subtitle", "")
            s_badge = s.get("badge", "")
            layout = s.get("layout", "card_grid")

            # Cover / Hero Slide Layout
            if idx == 0 or layout in ["cover", "hero", "title_slide"]:
                badge_text = s_badge or "PRODUCT LAUNCH"
                md_parts.append(f"<span class='px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'>{badge_text}</span>\n")
                md_parts.append(f"# <span class='bg-gradient-to-r {palette['gradient']} bg-clip-text text-transparent'>{s_title}</span>\n")
                if s_subtitle:
                    md_parts.append(f"<p class='text-base text-slate-400 mt-2 font-medium leading-relaxed'>{s_subtitle}</p>\n")
                
                content_items = s.get("content") or s.get("bullets") or []
                if isinstance(content_items, list) and content_items:
                    md_parts.append("<div class='mt-8 space-y-2'>")
                    for ci in content_items:
                        md_parts.append(f"  <div class='flex items-center gap-2 text-sm text-slate-300'><span class='text-cyan-400 font-bold'>&bull;</span> {ci}</div>")
                    md_parts.append("</div>\n")
                elif isinstance(content_items, str) and content_items:
                    md_parts.append(f"<p class='text-sm text-slate-300 mt-4 leading-relaxed'>{content_items}</p>\n")

                md_parts.append(f"<p class='text-xs text-slate-500 mt-10'>Author / Agent: {author}</p>\n")
                continue

            # Section Header
            if s_badge:
                md_parts.append(f"<span class='px-2.5 py-0.5 rounded-md text-xs font-bold tracking-wider uppercase bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'>{s_badge}</span>\n")

            md_parts.append(f"## {s_title}")
            if s_subtitle:
                md_parts.append(f"<p class='text-sm text-slate-400 mb-6'>{s_subtitle}</p>\n")

            # 1. Metrics / Stats Layout
            if layout in ["metrics", "metrics_3", "metrics_4", "stats"] or "metrics" in s:
                metrics = s.get("metrics", [])
                cols = min(max(len(metrics), 2), 4)
                md_parts.append(f"<div class='grid grid-cols-{cols} gap-4 my-6'>")
                for m in metrics:
                    val = m.get("value", "") if isinstance(m, dict) else str(m)
                    lbl = m.get("label", "") if isinstance(m, dict) else ""
                    sub = m.get("subtext", "") if isinstance(m, dict) else ""
                    md_parts.append(f"  <div class='p-5 rounded-2xl {card_bg}'>")
                    md_parts.append(f"    <div class='text-3xl font-extrabold text-cyan-400'>{val}</div>")
                    if lbl:
                        md_parts.append(f"    <div class='text-sm font-semibold text-white mt-1'>{lbl}</div>")
                    if sub:
                        md_parts.append(f"    <p class='text-xs {card_text} mt-2'>{sub}</p>")
                    md_parts.append("  </div>")
                md_parts.append("</div>\n")

            # 2. Timeline / Process Steps Layout
            elif layout in ["timeline", "process", "steps"] or "steps" in s:
                steps = s.get("steps", [])
                cols = min(max(len(steps), 2), 4)
                md_parts.append(f"<div class='grid grid-cols-{cols} gap-4 my-6'>")
                for s_idx, st in enumerate(steps, start=1):
                    st_title = st.get("title", "") if isinstance(st, dict) else str(st)
                    st_desc = st.get("content", "") or st.get("description", "") if isinstance(st, dict) else ""
                    md_parts.append(f"  <div class='p-5 rounded-2xl {card_bg} relative'>")
                    md_parts.append(f"    <div class='text-xs font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 w-max mb-2'>STEP 0{s_idx}</div>")
                    md_parts.append(f"    <h3 class='text-base font-bold text-white'>{st_title}</h3>")
                    if st_desc:
                        md_parts.append(f"    <p class='text-xs {card_text} mt-2'>{st_desc}</p>")
                    md_parts.append("  </div>")
                md_parts.append("</div>\n")

            # 3. Two Column Split / Comparison Layout
            elif layout in ["two_column", "split_2", "comparison"] or "column_1" in s or "column_left" in s or "left_content" in s:
                left_val = self._extract_column(s, "left")
                right_val = self._extract_column(s, "right")
                left_md = self._format_column_md(left_val)
                right_md = self._format_column_md(right_val)
                md_parts.append("<div class='grid grid-cols-2 gap-6 my-6'>")
                md_parts.append(f"  <div class='p-6 rounded-2xl {card_bg}'>\n{left_md}\n  </div>")
                md_parts.append(f"  <div class='p-6 rounded-2xl {card_bg}'>\n{right_md}\n  </div>")
                md_parts.append("</div>\n")

            # 4. Bento Grid or Card Grid Layout
            elif layout in ["card_grid", "cards_3", "cards_2", "bento_grid"] or "cards" in s:
                cards = s.get("cards", [])
                cols = 2 if layout == "cards_2" or len(cards) == 2 else 3
                md_parts.append(f"<div class='grid grid-cols-{cols} gap-4 my-6'>")
                for c in cards:
                    c_title = c.get("title", "") if isinstance(c, dict) else str(c)
                    c_desc = c.get("content", "") or c.get("description", "") if isinstance(c, dict) else ""
                    c_tag = c.get("tag", "") if isinstance(c, dict) else ""
                    c_points = c.get("points") or c.get("bullets") if isinstance(c, dict) else []
                    md_parts.append(f"  <div class='p-5 rounded-2xl {card_bg}'>")
                    if c_tag:
                        md_parts.append(f"    <span class='text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 uppercase'>{c_tag}</span>")
                    md_parts.append(f"    <h3 class='text-lg font-bold text-white mt-2'>{c_title}</h3>")
                    if c_desc:
                        md_parts.append(f"    <p class='text-xs {card_text} mt-2 leading-relaxed'>{c_desc}</p>")
                    if c_points:
                        for p in c_points:
                            md_parts.append(f"    <p class='text-xs text-slate-400 mt-1'>&bull; {p}</p>")
                    md_parts.append("  </div>")
                md_parts.append("</div>\n")

            # 5. Standard Content
            else:
                content = s.get("content", "")
                if isinstance(content, list):
                    for ci in content:
                        md_parts.append(f"- {ci}")
                elif content:
                    md_parts.append(f"{content}\n")
                bullets = s.get("bullet_list", []) or s.get("items", [])
                for b in bullets:
                    md_parts.append(f"- {b}")
                md_parts.append("")

        return "\n".join(md_parts)

    # =========================================================================
    # 4. Standalone Interactive Gamma HTML5 Slide Deck Generator
    # =========================================================================

    def generate_standalone_html(
        self,
        title: str,
        slides: List[Dict[str, Any]],
        theme_name: str = "dark_executive",
        author: str = "NAVA Engineering Intelligence",
        custom_theme: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Builds a bespoke, interactive HTML5 Presentation Deck with dynamic palette,
        responsive cards, fullscreen toggle, and pixel-perfect widescreen print styling.
        """
        palette = self._resolve_palette(theme_name, custom_theme)
        slides_html_list = []

        for idx, s in enumerate(slides):
            s_title = s.get("title", f"Slide {idx + 1}")
            s_subtitle = s.get("subtitle", "")
            s_badge = s.get("badge", "")
            layout = s.get("layout", "card_grid")
            content_html = ""

            # 0. Hero / Cover Slide Layout
            if idx == 0 or layout in ["cover", "hero", "title_slide"]:
                badge_text = s_badge or "EXECUTIVE INTELLIGENCE"
                content_items = s.get("content") or s.get("bullets") or []
                takeaways_html = ""
                if isinstance(content_items, list) and content_items:
                    pills = "".join([f"<div class='flex items-center gap-2 text-xs md:text-sm text-slate-300'><span class='text-cyan-400 font-bold'>&bull;</span><span>{ci}</span></div>" for ci in content_items])
                    takeaways_html = f"<div class='mt-6 space-y-2 max-w-2xl bg-slate-800/40 p-4 rounded-xl border border-slate-700/50'>{pills}</div>"
                elif isinstance(content_items, str) and content_items:
                    takeaways_html = f"<p class='text-sm text-slate-300 mt-4 max-w-2xl leading-relaxed'>{content_items}</p>"

                hero_slide = f"""
                <div class="slide {'active' if idx == 0 else ''}" id="slide-{idx}">
                    <div class="slide-content flex flex-col justify-center h-full max-w-4xl mx-auto">
                        <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold tracking-wider uppercase {palette['tag_bg']} border w-max mb-6">
                            <span>✨</span> {badge_text}
                        </div>
                        <h1 class="text-4xl md:text-5xl font-extrabold tracking-tight bg-gradient-to-r {palette['gradient']} bg-clip-text text-transparent leading-tight mb-4">
                            {s_title}
                        </h1>
                        {f'<p class="text-lg text-slate-300 font-medium leading-relaxed max-w-3xl mb-4">{s_subtitle}</p>' if s_subtitle else ''}
                        {takeaways_html}
                        <div class="pt-8 mt-6 border-t border-slate-800 flex items-center justify-between text-xs text-slate-500">
                            <div>Author: <span class="text-slate-300 font-semibold">{author}</span></div>
                            <div class="font-mono text-slate-400">NAVA Presentation OS</div>
                        </div>
                    </div>
                </div>
                """
                slides_html_list.append(hero_slide)
                continue

            # 1. Metrics Grid
            if layout in ["metrics", "metrics_3", "metrics_4", "stats"] or "metrics" in s:
                metrics = s.get("metrics", [])
                cols = min(max(len(metrics), 2), 4)
                cards_html = []
                for m in metrics:
                    val = m.get("value", "") if isinstance(m, dict) else str(m)
                    lbl = m.get("label", "") if isinstance(m, dict) else ""
                    sub = m.get("subtext", "") if isinstance(m, dict) else ""
                    cards_html.append(f"""
                    <div class="metric-card p-6 rounded-2xl border flex flex-col justify-between">
                        <div class="text-3xl md:text-4xl font-extrabold text-cyan-400 tracking-tight">{val}</div>
                        <div class="mt-2">
                            <div class="text-sm font-bold text-slate-200">{lbl}</div>
                            {f'<div class="text-xs text-slate-400 mt-1">{sub}</div>' if sub else ''}
                        </div>
                    </div>
                    """)
                content_html = f'<div class="grid grid-cols-1 md:grid-cols-{cols} gap-4 my-6">{"".join(cards_html)}</div>'

            # 2. Timeline / Process Flow
            elif layout in ["timeline", "process", "steps"] or "steps" in s:
                steps = s.get("steps", [])
                cols = min(max(len(steps), 2), 4)
                steps_html = []
                for s_idx, st in enumerate(steps, start=1):
                    st_title = st.get("title", "") if isinstance(st, dict) else str(st)
                    st_desc = st.get("content", "") or st.get("description", "") if isinstance(st, dict) else ""
                    steps_html.append(f"""
                    <div class="card p-6 rounded-2xl border flex flex-col justify-between">
                        <div class="text-xs font-mono font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 w-max mb-3">STEP 0{s_idx}</div>
                        <div>
                            <h3 class="text-base font-bold text-slate-100 mb-2">{st_title}</h3>
                            <p class="text-xs text-slate-300 leading-relaxed">{st_desc}</p>
                        </div>
                    </div>
                    """)
                content_html = f'<div class="grid grid-cols-1 md:grid-cols-{cols} gap-4 my-6">{"".join(steps_html)}</div>'

            # 3. Two Column Split / Comparison
            elif layout in ["two_column", "split_2", "comparison"] or "column_1" in s or "column_left" in s or "left_content" in s:
                left_val = self._extract_column(s, "left")
                right_val = self._extract_column(s, "right")
                left_html = self._format_column_html(left_val, palette, is_left=True)
                right_html = self._format_column_html(right_val, palette, is_left=False)
                content_html = f"""
                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 my-6">
                    <div class="card p-6 rounded-2xl border">{left_html}</div>
                    <div class="card p-6 rounded-2xl border">{right_html}</div>
                </div>
                """

            # 4. Bento / Feature Card Grid
            elif layout in ["card_grid", "cards_3", "cards_2", "bento_grid"] or "cards" in s:
                cards = s.get("cards", [])
                cols = 2 if layout == "cards_2" or len(cards) == 2 else 3
                cards_html = []
                for c in cards:
                    c_title = c.get("title", "") if isinstance(c, dict) else str(c)
                    c_desc = c.get("content", "") or c.get("description", "") if isinstance(c, dict) else ""
                    c_tag = c.get("tag", "") if isinstance(c, dict) else ""
                    c_points = c.get("points") or c.get("bullets") if isinstance(c, dict) else []
                    points_html = "".join([f"<li class='text-[11px] text-slate-400 mt-1 flex items-center gap-1.5'><span class='text-cyan-400'>&bull;</span>{p}</li>" for p in c_points]) if c_points else ""
                    cards_html.append(f"""
                    <div class="card p-6 rounded-2xl border flex flex-col">
                        {f'<div class="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 w-max mb-3 uppercase tracking-wider">{c_tag}</div>' if c_tag else ''}
                        <h3 class="text-lg font-bold text-slate-100 mb-2">{c_title}</h3>
                        {f'<p class="text-xs text-slate-300 leading-relaxed">{c_desc}</p>' if c_desc else ''}
                        {f'<ul class="mt-2 space-y-0.5">{points_html}</ul>' if points_html else ''}
                    </div>
                    """)
                content_html = f'<div class="grid grid-cols-1 md:grid-cols-{cols} gap-4 my-6">{"".join(cards_html)}</div>'

            # 5. Standard
            else:
                body_p = f'<p class="text-sm text-slate-300 leading-relaxed mb-4">{s.get("content", "")}</p>' if s.get("content") else ""
                bullets = s.get("bullet_list", []) or s.get("items", [])
                bullet_items = "".join([f'<li class="flex items-start gap-2 text-sm text-slate-300 mb-2.5"><span class="text-cyan-400 font-bold">&bull;</span><span>{b}</span></li>' for b in bullets])
                bullets_html = f'<ul class="space-y-1 my-4">{bullet_items}</ul>' if bullet_items else ""
                content_html = f'<div class="card p-8 rounded-2xl border max-w-4xl">{body_p}{bullets_html}</div>'

            badge_html = f"<span class='text-xs font-bold tracking-widest uppercase {palette['tag_bg']} px-2.5 py-1 rounded-md border'>{s_badge}</span>" if s_badge else f"<span class='text-xs font-bold tracking-widest uppercase {palette['tag_bg']} px-2.5 py-1 rounded-md border'>SLIDE {idx:02d}</span>"

            slide_body = f"""
            <div class="slide {'active' if idx == 0 else ''}" id="slide-{idx}">
                <div class="slide-content flex flex-col justify-center h-full max-w-5xl mx-auto">
                    <div class="flex items-center justify-between mb-3">
                        {badge_html}
                        <span class="text-xs text-slate-500 font-mono">Slide {idx + 1} of {len(slides)}</span>
                    </div>
                    <h2 class="text-2xl md:text-3xl font-bold text-slate-100 tracking-tight">{s_title}</h2>
                    {f'<p class="text-xs md:text-sm text-slate-400 mt-1">{s_subtitle}</p>' if s_subtitle else ''}
                    {content_html}
                </div>
            </div>
            """
            slides_html_list.append(slide_body)

        total_count = len(slides_html_list)

        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
        * {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            box-sizing: border-box;
        }}
        body {{
            background-color: {palette['bg_main']};
            color: {palette['text_primary']};
            overflow: hidden;
            user-select: none;
        }}
        .deck-container {{
            position: relative;
            width: 100vw;
            height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .slide {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            padding: 2.5rem;
            display: none;
            opacity: 0;
            transform: scale(0.98);
            transition: opacity 0.35s ease, transform 0.35s ease;
            background-color: {palette['slide_bg']};
        }}
        .slide.active {{
            display: flex;
            opacity: 1;
            transform: scale(1);
        }}
        .card, .metric-card {{
            background: {palette['card_bg']};
            border-color: {palette['card_border']};
            backdrop-filter: blur(12px);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }}
        .card:hover, .metric-card:hover {{
            transform: translateY(-2px);
            border-color: {palette['accent']};
        }}
        /* Navigation Controls */
        .controls {{
            position: fixed;
            bottom: 1.5rem;
            right: 1.5rem;
            z-index: 50;
            display: flex;
            align-items: center;
            gap: 0.5rem;
            background: rgba(15, 23, 42, 0.85);
            backdrop-filter: blur(8px);
            padding: 0.4rem 0.8rem;
            border-radius: 9999px;
            border: 1px solid rgba(71, 85, 105, 0.5);
        }}
        .progress-bar {{
            position: fixed;
            bottom: 0;
            left: 0;
            height: 4px;
            background: linear-gradient(90deg, {palette['accent']}, {palette['accent_secondary']});
            transition: width 0.3s ease;
            z-index: 50;
        }}
        @media print {{
            @page {{
                size: 16in 9in;
                margin: 0;
            }}
            *, *:before, *:after {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
            }}
            html, body {{
                width: 100% !important;
                height: auto !important;
                min-height: 100% !important;
                overflow: visible !important;
                background-color: {palette['slide_bg']} !important;
                margin: 0 !important;
                padding: 0 !important;
            }}
            .deck-container {{
                display: block !important;
                position: static !important;
                width: 100% !important;
                height: auto !important;
                overflow: visible !important;
            }}
            .slide {{
                position: relative !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: center !important;
                opacity: 1 !important;
                transform: none !important;
                width: 100vw !important;
                height: 100vh !important;
                min-height: 100vh !important;
                max-height: 100vh !important;
                page-break-after: always !important;
                page-break-inside: avoid !important;
                break-after: page !important;
                break-inside: avoid !important;
                background-color: {palette['slide_bg']} !important;
                padding: 3rem 4rem !important;
                box-sizing: border-box !important;
            }}
            .controls, .progress-bar {{ display: none !important; }}
            .card, .metric-card {{
                background: {palette['card_bg']} !important;
                border-color: {palette['card_border']} !important;
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
            }}
        }}
    </style>
</head>
<body>
    <div class="deck-container">
        {"".join(slides_html_list)}
    </div>

    <!-- Controls Bar -->
    <div class="controls text-xs font-semibold text-slate-300">
        <button onclick="prevSlide()" class="p-1.5 hover:text-cyan-400 transition" title="Previous Slide (← / Space)">❮</button>
        <span id="slide-indicator" class="px-2 font-mono">1 / {total_count}</span>
        <button onclick="nextSlide()" class="p-1.5 hover:text-cyan-400 transition" title="Next Slide (→ / Enter)">❯</button>
        <button onclick="toggleFullscreen()" class="p-1.5 hover:text-cyan-400 transition border-l border-slate-700 pl-2" title="Fullscreen (F)">⛶</button>
    </div>

    <!-- Progress Indicator -->
    <div id="progress-bar" class="progress-bar" style="width: {(1/total_count)*100}%;"></div>

    <script>
        let currentSlide = 0;
        const totalSlides = {total_count};

        function showSlide(index) {{
            if (index < 0 || index >= totalSlides) return;
            document.querySelectorAll('.slide').forEach((el, i) => {{
                el.classList.toggle('active', i === index);
            }});
            currentSlide = index;
            document.getElementById('slide-indicator').innerText = `${{index + 1}} / ${{totalSlides}}`;
            document.getElementById('progress-bar').style.width = `${{((index + 1) / totalSlides) * 100}}%`;
        }}

        function nextSlide() {{
            if (currentSlide < totalSlides - 1) showSlide(currentSlide + 1);
        }}

        function prevSlide() {{
            if (currentSlide > 0) showSlide(currentSlide - 1);
        }}

        function toggleFullscreen() {{
            if (!document.fullscreenElement) {{
                document.documentElement.requestFullscreen().catch(() => {{}});
            }} else {{
                document.exitFullscreen().catch(() => {{}});
            }}
        }}

        // Keyboard navigation
        document.addEventListener('keydown', (e) => {{
            if (['ArrowRight', 'Space', 'PageDown', 'Enter'].includes(e.key)) {{
                e.preventDefault();
                nextSlide();
            }} else if (['ArrowLeft', 'PageUp', 'Backspace'].includes(e.key)) {{
                e.preventDefault();
                prevSlide();
            }} else if (e.key === 'f' || e.key === 'F') {{
                toggleFullscreen();
            }}
        }});
    </script>
</body>
</html>"""
        return html_template

    # =========================================================================
    # 5. Modernized PPTX Generator (Enhanced python-pptx Card Layouts)
    # =========================================================================

    def _generate_modern_pptx(
        self,
        filename: str,
        title: str,
        slides: List[Dict[str, Any]],
        theme_name: str = "dark_executive",
        custom_theme: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generates modern 16:9 widescreen PPTX decks with sleek dark backgrounds,
        rounded metric cards, accent banners, and high-contrast typography.
        """
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
            from pptx.dml.color import RGBColor
        except ImportError:
            return filename

        palette = self._resolve_palette(theme_name, custom_theme)

        def hex_to_rgb(hex_str: str) -> Optional[RGBColor]:
            if not hex_str:
                return None
            hex_str = str(hex_str).lstrip("#")
            if len(hex_str) != 6:
                return None
            try:
                return RGBColor(int(hex_str[0:2], 16), int(hex_str[2:4], 16), int(hex_str[4:6], 16))
            except ValueError:
                return None

        bg_rgb = hex_to_rgb(palette["slide_bg"]) or RGBColor(15, 23, 42)
        title_rgb = hex_to_rgb(palette["text_primary"]) or RGBColor(248, 250, 252)
        text_rgb = hex_to_rgb(palette["text_secondary"]) or RGBColor(148, 163, 184)
        accent_rgb = hex_to_rgb(palette["accent"]) or RGBColor(56, 189, 248)
        card_bg_rgb = hex_to_rgb("#1E293B") or RGBColor(30, 41, 59)

        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)
        blank_layout = prs.slide_layouts[6]

        def apply_background(slide):
            fill = slide.background.fill
            fill.solid()
            fill.fore_color.rgb = bg_rgb

        for idx, s in enumerate(slides):
            slide = prs.slides.add_slide(blank_layout)
            apply_background(slide)

            s_title = s.get("title", f"Slide {idx + 1}")
            s_subtitle = s.get("subtitle", "")
            s_badge = s.get("badge", "")
            layout = s.get("layout", "card_grid")

            # Cover / Hero Slide
            if idx == 0 or layout in ["cover", "hero", "title_slide"]:
                top_line = slide.shapes.add_shape(1, Inches(1.2), Inches(1.5), Inches(2.0), Inches(0.08))
                top_line.fill.solid()
                top_line.fill.fore_color.rgb = accent_rgb
                top_line.line.fill.background()

                title_box = slide.shapes.add_textbox(Inches(1.2), Inches(2.0), Inches(10.5), Inches(3.0))
                tf = title_box.text_frame
                tf.word_wrap = True
                p0 = tf.paragraphs[0]
                p0.text = s_title
                p0.font.size = Pt(40)
                p0.font.bold = True
                p0.font.color.rgb = title_rgb

                if s_subtitle:
                    p1 = tf.add_paragraph()
                    p1.text = s_subtitle
                    p1.font.size = Pt(18)
                    p1.font.color.rgb = text_rgb

                content_items = s.get("content") or s.get("bullets") or []
                if isinstance(content_items, list):
                    for ci in content_items:
                        p_ci = tf.add_paragraph()
                        p_ci.text = f"• {ci}"
                        p_ci.font.size = Pt(13)
                        p_ci.font.color.rgb = text_rgb
                continue

            # Standard Slide Header
            header_box = slide.shapes.add_textbox(Inches(1.0), Inches(0.8), Inches(11.3), Inches(1.4))
            htf = header_box.text_frame
            htf.word_wrap = True
            hp0 = htf.paragraphs[0]
            badge_prefix = f"{s_badge}  |  " if s_badge else ""
            hp0.text = f"{badge_prefix}{s_title}"
            hp0.font.size = Pt(26)
            hp0.font.bold = True
            hp0.font.color.rgb = title_rgb

            if s_subtitle:
                hp1 = htf.add_paragraph()
                hp1.text = s_subtitle
                hp1.font.size = Pt(13)
                hp1.font.color.rgb = text_rgb

            # Layout: Metrics / Stats
            if layout in ["metrics", "metrics_3", "metrics_4", "stats"] or "metrics" in s:
                metrics = s.get("metrics", [])
                cols = min(max(len(metrics), 2), 4)
                card_w = (11.3 - (0.3 * (cols - 1))) / cols
                for m_idx, m in enumerate(metrics[:cols]):
                    val = m.get("value", "") if isinstance(m, dict) else str(m)
                    lbl = m.get("label", "") if isinstance(m, dict) else ""
                    sub = m.get("subtext", "") if isinstance(m, dict) else ""

                    left = Inches(1.0 + (m_idx * (card_w + 0.3)))
                    top = Inches(2.6)
                    card = slide.shapes.add_shape(1, left, top, Inches(card_w), Inches(3.6))
                    card.fill.solid()
                    card.fill.fore_color.rgb = card_bg_rgb
                    card.line.fill.background()

                    ctf = card.text_frame
                    ctf.word_wrap = True
                    cp0 = ctf.paragraphs[0]
                    cp0.text = str(val)
                    cp0.font.size = Pt(36)
                    cp0.font.bold = True
                    cp0.font.color.rgb = accent_rgb

                    cp1 = ctf.add_paragraph()
                    cp1.text = str(lbl)
                    cp1.font.size = Pt(16)
                    cp1.font.bold = True
                    cp1.font.color.rgb = title_rgb

                    if sub:
                        cp2 = ctf.add_paragraph()
                        cp2.text = str(sub)
                        cp2.font.size = Pt(11)
                        cp2.font.color.rgb = text_rgb

            # Layout: Two Column Split
            elif layout in ["two_column", "split_2", "comparison"] or "column_1" in s or "column_left" in s or "left_content" in s:
                left_val = self._extract_column(s, "left")
                right_val = self._extract_column(s, "right")

                for col_idx, c_data in enumerate([left_val, right_val]):
                    c_left = Inches(1.0 + (col_idx * 5.8))
                    card = slide.shapes.add_shape(1, c_left, Inches(2.4), Inches(5.5), Inches(4.2))
                    card.fill.solid()
                    card.fill.fore_color.rgb = card_bg_rgb
                    card.line.fill.background()

                    ctf = card.text_frame
                    ctf.word_wrap = True

                    if isinstance(c_data, dict):
                        cp0 = ctf.paragraphs[0]
                        cp0.text = str(c_data.get("title") or c_data.get("header") or "")
                        cp0.font.size = Pt(18)
                        cp0.font.bold = True
                        cp0.font.color.rgb = title_rgb

                        if c_data.get("subtitle"):
                            cp_sub = ctf.add_paragraph()
                            cp_sub.text = str(c_data.get("subtitle"))
                            cp_sub.font.size = Pt(11)
                            cp_sub.font.color.rgb = accent_rgb

                        points = c_data.get("points") or c_data.get("bullets") or c_data.get("items") or []
                        for p in points:
                            bp = ctf.add_paragraph()
                            bp.text = f"• {p}"
                            bp.font.size = Pt(11)
                            bp.font.color.rgb = text_rgb
                    else:
                        cp0 = ctf.paragraphs[0]
                        cp0.text = str(c_data)
                        cp0.font.size = Pt(12)
                        cp0.font.color.rgb = text_rgb

            # Layout: Cards Grid
            elif layout in ["card_grid", "cards_3", "cards_2", "bento_grid"] or "cards" in s:
                cards = s.get("cards", [])
                cols = 2 if layout == "cards_2" or len(cards) == 2 else 3
                card_w = (11.3 - (0.4 * (cols - 1))) / cols
                for c_idx, c in enumerate(cards[:cols]):
                    c_title = c.get("title", "") if isinstance(c, dict) else str(c)
                    c_desc = c.get("content", "") or c.get("description", "") if isinstance(c, dict) else ""

                    left = Inches(1.0 + (c_idx * (card_w + 0.4)))
                    top = Inches(2.5)
                    card = slide.shapes.add_shape(1, left, top, Inches(card_w), Inches(3.8))
                    card.fill.solid()
                    card.fill.fore_color.rgb = card_bg_rgb
                    card.line.fill.background()

                    ctf = card.text_frame
                    ctf.word_wrap = True
                    cp0 = ctf.paragraphs[0]
                    cp0.text = str(c_title)
                    cp0.font.size = Pt(18)
                    cp0.font.bold = True
                    cp0.font.color.rgb = title_rgb

                    if c_desc:
                        cp1 = ctf.add_paragraph()
                        cp1.text = str(c_desc)
                        cp1.font.size = Pt(12)
                        cp1.font.color.rgb = text_rgb

            # Default Standard / Bullets
            else:
                body_card = slide.shapes.add_shape(1, Inches(1.0), Inches(2.4), Inches(11.3), Inches(4.0))
                body_card.fill.solid()
                body_card.fill.fore_color.rgb = card_bg_rgb
                body_card.line.fill.background()

                btf = body_card.text_frame
                btf.word_wrap = True
                content = s.get("content", "")
                if content:
                    bp0 = btf.paragraphs[0]
                    bp0.text = str(content)
                    bp0.font.size = Pt(14)
                    bp0.font.color.rgb = title_rgb

                bullets = s.get("bullet_list", []) or s.get("items", [])
                for b in bullets:
                    bp = btf.add_paragraph()
                    bp.text = f"•  {b}"
                    bp.font.size = Pt(13)
                    bp.font.color.rgb = text_rgb

        prs.save(filename)
        return filename

    # =========================================================================
    # 6. Parser Helper for Slidev Markdown
    # =========================================================================

    def _parse_slidev_to_slides(self, markdown_text: str) -> Dict[str, Any]:
        """Parses Slidev markdown slides into structured slide definitions."""
        raw_slides = markdown_text.split("\n---")
        title = "Executive Presentation"
        slides = []

        for idx, s_raw in enumerate(raw_slides):
            text = s_raw.strip()
            if not text:
                continue

            if idx == 0 or ("# " in text and not slides):
                t_match = re.search(r'#\s+([^\n\r<]+)', text)
                if t_match:
                    title = t_match.group(1).strip()

            s_title = "Slide"
            h2_match = re.search(r'##\s+([^\n\r<]+)', text) or re.search(r'#\s+([^\n\r<]+)', text)
            if h2_match:
                s_title = h2_match.group(1).strip()

            bullets = re.findall(r'^\s*-\s+(.+)$', text, re.MULTILINE)
            content_cleaned = re.sub(r'<[^>]+>', '', text)
            content_cleaned = re.sub(r'#+\s+[^\n\r]+', '', content_cleaned).strip()

            slides.append({
                "title": s_title,
                "badge": f"SLIDE {len(slides) + 1:02d}",
                "content": content_cleaned[:300] if content_cleaned else "",
                "bullet_list": bullets
            })

        return {"title": title, "slides": slides}
