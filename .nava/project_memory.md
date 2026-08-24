# 📌 Project Workspace Memory: Nava

## 🎯 1. Project Overview & Architecture
- **Project Name**: Nava
- **Root Directory**: `C:\Users\aakhi\Desktop\Nava`
- **Primary Goal**: Autonomous workspace execution for Nava Personal Agent OS.
- **Tech Stack**: Python, LangGraph, Playwright, MCP
- **Total Indexed Files**: 119

## 📝 2. Architectural Decisions & Constraints
- *Decision 1*: All file mutations are governed by NAVA Action Gateway and concurrency locks.
- *Decision 2*: All task deliverables and outputs are isolated in `.nava/tasks/<task_id>/artifacts/`.
- *Constraint 1*: Operations must remain confined within the workspace root.