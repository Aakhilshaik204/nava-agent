"""
graph_dispatcher.py — Centralized Registry for Agent Runtime Graphs.
Decouples agent graph resolution from the Orchestrator.
"""
from typing import Optional, Callable
from langgraph.graph import StateGraph
from nava.tools.registry import ToolRegistry

from nava.agents.runtime.coding_agent import build_coding_agent
from nava.agents.runtime.reviewer_agent import build_reviewer_agent
from nava.agents.runtime.data_agent import build_data_agent
from nava.agents.runtime.document_agent import build_document_agent
from nava.agents.runtime.research_agent import build_research_agent
from nava.agents.runtime.browser_agent import build_browser_agent
from nava.agents.runtime.computer_agent import build_computer_agent
from nava.agents.runtime.terminal_agent import build_terminal_agent
from nava.agents.runtime.dynamic_agent import build_dynamic_agent
from nava.agents.runtime.verifier_agent import build_verifier_agent
from nava.agents.runtime.file_agent import build_file_agent
from nava.agents.runtime.nava_agent import build_nava_agent

_GRAPH_FACTORIES = {
    "DocumentAgent": lambda reg: build_document_agent(reg),
    "DataAgent": lambda reg: build_data_agent(reg),
    "VerifierAgent": lambda reg: build_verifier_agent(reg),
    "UniversalFileAgent": lambda reg: build_file_agent(),
    "CodingAgent": lambda reg: build_coding_agent(reg),
    "ReviewerAgent": lambda reg: build_reviewer_agent(reg),
    "BrowserAgent": lambda reg: build_browser_agent(reg),
    "ResearchAgent": lambda reg: build_research_agent(reg),
    "ComputerAgent": lambda reg: build_computer_agent(reg),
    "TerminalAgent": lambda reg: build_terminal_agent(reg),
    "DynamicAgent": lambda reg: build_dynamic_agent(reg),
}

def get_agent_graph(role: str, registry: Optional[ToolRegistry] = None) -> StateGraph:
    """Returns the compiled LangGraph execution graph for the requested agent role."""
    factory = _GRAPH_FACTORIES.get(role)
    if factory:
        return factory(registry)
    return build_nava_agent()
