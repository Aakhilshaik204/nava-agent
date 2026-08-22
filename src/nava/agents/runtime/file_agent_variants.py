"""
file_agent_variants.py — Named variants of the file-producing agent.

DocumentAgent, DataAgent, and VerifierAgent all share the same file_agent
graph but are distinguished by the role name injected into their AgentState,
which informs the LLM prompt about context.
"""
from langgraph.graph import StateGraph
from nava.agents.runtime.file_agent import build_file_agent


def build_document_agent() -> StateGraph:
    """Agent that reads and summarizes content into structured file outputs."""
    return build_file_agent()


def build_data_agent() -> StateGraph:
    """Agent that analyzes data and produces analytical file reports."""
    return build_file_agent()


def build_verifier_agent() -> StateGraph:
    """Agent that verifies outputs and produces structured validation reports."""
    return build_file_agent()
