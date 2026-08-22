"""
NAVA OS Workspace & Context Continuity Subsystem.
Manages project root binding, AST indexing, and persistent .nava/project_memory.md checkpoints.
"""

from nava.workspace.project_manager import ProjectWorkspace
from nava.workspace.indexer import ProjectIndexer

__all__ = ["ProjectWorkspace", "ProjectIndexer"]
