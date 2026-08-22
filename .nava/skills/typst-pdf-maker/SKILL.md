---
name: typst-pdf-maker
description: "Generate professional, high-quality PDF documents with Typst. Use for reports, academic papers, resumes, structured documents, mathematical typesetting, code-rich documents, precise layouts, and CJK typography when Markdown-to-PDF is insufficient."
---
# Typst PDF Maker
Use Typst and Python PDF generators for polished, structured PDF documents requiring precise typography or executive layout control.

## Fixed Save Destination
All generated PDF files and document artifacts MUST be saved by default to the local scratch directory: `scratch/`

## Fast Implementation Workflow
Use the bundled scripts in `scripts/` and resources in `assets/` / `references/` for fast execution.
**CRITICAL FOR PLANNER:** You MUST assign this task to a `CodingAgent` because it requires the `shell.execute` permission to run the Python scripts!

**CRITICAL FOR AGENT:** Do NOT hallucinate tools! You MUST use the `shell.execute` tool to run the scripts.
Example: `shell.execute(command="python3 .nava/skills/typst-pdf-maker/scripts/generate_pdf.py --data_file scratch/data.json --output scratch/sample.pdf")`

**STEP 1: Generate Content (Crucial!)**
Before compiling the PDF, you MUST use `file.write` to create a `scratch/data.json` file containing your generated content.
The JSON must follow this EXACT schema. Note that 'content' can contain strings (paragraphs), code blocks, or tables:
```json
{
  "callout_text": "A brief summary highlight...",
  "metrics": [
    {"label": "Metric Name", "value": "100", "delta": "+5%"}
  ],
  "sections": [
    {
      "heading": "1. Introduction",
      "content": [
        "Paragraph 1 text here.",
        {
          "type": "code",
          "code": "print('Hello World')"
        }
      ]
    },
    {
      "heading": "2. Data Matrix",
      "content": [
        {
          "type": "table",
          "data": [
            ["Column 1", "Column 2", "Column 3"],
            ["Row 1", "Data", "Data"]
          ],
          "widths": [100, 200, 100]
        }
      ]
    }
  ]
}
```

**STEP 2: Fast PDF Compilation Script** (`scripts/generate_pdf.py`): 
Runs Python PDF compilation and injects your `data.json` file.
```bash
python3 .nava/skills/typst-pdf-maker/scripts/generate_pdf.py \
  --output "scratch/sample.pdf" \
  --data_file "scratch/data.json" \
  --title "Document Title" \
  --subtitle "Subtitle" \
  --author "Author" \
  --date "August 2026"
```

Project Preparation Script (`scripts/prepare_document.py`): Sets up a complete document project with main.typ, report-theme.typ, and content manifest.
```bash
python3 .nava/skills/typst-pdf-maker/scripts/prepare_document.py \
  scratch/project_dir \
  --title "Document Title" \
  --subtitle "Subtitle" \
  --author "Author" \
  --date "August 2026"
```

Planner Script (scripts/plan_document.py): Generates content manifest and build plan for layout routing.

python3 skills/typst-pdf-maker/scripts/plan_document.py \

  .typst-content-manifest.json \

  --output .typst-build-plan.json
Bundled Scripts & Resources
Path
Description
scripts/generate_pdf.py
Standalone high-speed PDF generator script for executive reports
scripts/prepare_document.py
Project scaffold script creating main.typ and report-theme.typ
scripts/plan_document.py
Manifest planner and build routing script
assets/report_theme_typ.txt
Shared Typst visual theme definition with brand styling
assets/report_entry_typ.txt
Native report entry point template
assets/markdown_entry_typ.txt
Markdown adapter template
references/routing-catalog.json
Local asset and package registry catalog
