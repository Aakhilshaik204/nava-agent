from typing import List, Dict, Any, Optional
from pydantic import BaseModel

class StaticAgentTemplate(BaseModel):
    """
    Governance registry definition for static agents.
    This class defines the identity and strictly bounded permission scope of an agent.
    It does NOT contain the execution logic.
    """
    # Acts as the explicit pointer/registry-key to the actual LangGraph implementation
    # e.g., template_id="coding_agent" -> maps to graph_registry.get("coding_agent")
    template_id: str
    role: str
    permission_scope: List[str]
    default_system_prompt: str


class Templates:
    CodingAgent = StaticAgentTemplate(
        template_id="coding_agent",
        role="Code modification and analysis",
        permission_scope=["filesystem.read", "filesystem.write", "test.run", "ast.read", "ast.write", "git.read", "git.write", "github.*", "subagent.spawn"],
        default_system_prompt="You are a coding agent..."
    )
    
    ComputerAgent = StaticAgentTemplate(
        template_id="computer_agent",
        role="General computer operation and OS GUI automation",
        permission_scope=["desktop.*", "filesystem.read"],
        default_system_prompt="You are a computer use agent..."
    )
    
    TerminalAgent = StaticAgentTemplate(
        template_id="terminal_agent",
        role="DevOps, build and test execution, git workflows, and compilation error diagnostics",
        permission_scope=["shell.execute", "terminal.execute", "test.run", "git.read", "filesystem.read"],
        default_system_prompt="You are a terminal agent..."
    )
    
    ReviewerAgent = StaticAgentTemplate(
        template_id="reviewer_agent",
        role="Deep code review, security AST vulnerability inspection, and sequential reasoning audit",
        permission_scope=["filesystem.read", "github.read", "reasoning.sequential", "audit.security", "sequential_thinking.*", "audit.*", "subagent.spawn"],
        default_system_prompt="You review code, inspect AST security risks, and execute sequential thinking reasoning."
    )
    
    ResearchAgent = StaticAgentTemplate(
        template_id="research_agent",
        role="Deep web and document research, cross-referencing, and synthesis",
        permission_scope=["research.read", "fetch.*", "brave.*", "arxiv.*", "browser.*", "search.web", "memory.semantic", "filesystem.read", "filesystem.write", "subagent.spawn"],
        default_system_prompt="You are a researcher..."
    )
    
    DocumentAgent = StaticAgentTemplate(
        template_id="document_agent",
        role="Publication-grade Typst document design, PDF compilation, DOCX/PPTX generation, and executive document synthesis",
        permission_scope=["document.compile", "document.read", "typst.*", "doc.*", "presentation.*", "filesystem.read", "filesystem.write", "subagent.spawn"],
        default_system_prompt="You are an expert document designer specializing in publication-grade Typst compilation and executive document rendering."
    )
    
    VerifierAgent = StaticAgentTemplate(
        template_id="verifier_agent",
        role="Deterministic task verification, 21-system-invariant auditing, and semantic grounding reconciliation",
        permission_scope=["filesystem.read", "test.run", "audit.verify", "reasoning.sequential", "sequential_thinking.*", "audit.*", "subagent.spawn"],
        default_system_prompt="You verify task completion, audit system invariants, and validate semantic grounding."
    )
    
    BrowserAgent = StaticAgentTemplate(
        template_id="browser_agent",
        role="Web navigation and extraction",
        permission_scope=["browser.*"],
        default_system_prompt="You operate a browser..."
    )
    
    DataAgent = StaticAgentTemplate(
        template_id="data_agent",
        role="Data analysis, SQL database operations, and tabular transformation",
        permission_scope=["data.analyze", "database.read", "database.write", "sqlite.*", "data.*", "filesystem.read", "filesystem.write", "python.execute", "subagent.spawn"],
        default_system_prompt="You analyze data and execute SQL database operations..."
    )
    
    FileAgent = StaticAgentTemplate(
        template_id="file_agent",
        role="General file management",
        permission_scope=["filesystem.*"],
        default_system_prompt="You manage files..."
    )
    
    UniversalFileAgent = StaticAgentTemplate(
        template_id="universal_file_agent",
        role="Document/data file generation across formats (PDF, Typst, DOCX, PPTX, TXT, MD, HTML Presentations)",
        permission_scope=["filesystem.write", "filesystem.read", "document.compile", "typst.*", "doc.*", "presentation.*"],
        default_system_prompt="You generate files in requested formats including Typst, PDF, DOCX, PPTX, and Gamma-style HTML/Slidev presentations..."
    )
    
    EmailAgent = StaticAgentTemplate(
        template_id="email_agent",
        role="Email communication",
        permission_scope=["gmail.*"],
        default_system_prompt="You manage emails..."
    )
    
    CalendarAgent = StaticAgentTemplate(
        template_id="calendar_agent",
        role="Calendar management",
        permission_scope=["calendar.*"],
        default_system_prompt="You manage calendar events..."
    )
    
    TerminalAgent = StaticAgentTemplate(
        template_id="terminal_agent",
        role="DevOps, test runner, environment diagnostics, and ephemeral Docker sandbox management",
        permission_scope=["terminal.execute", "test.run", "docker.sandbox", "system.inspect", "filesystem.read", "filesystem.write", "git.read"],
        default_system_prompt="You are an expert DevOps engineer and terminal specialist managing test suites, process execution, and ephemeral Docker sandboxes."
    )
    
    GitHubAgent = StaticAgentTemplate(
        template_id="github_agent",
        role="GitHub operations",
        permission_scope=["github.*"],
        default_system_prompt="You manage repositories..."
    )

    @classmethod
    def get_all(cls) -> List[StaticAgentTemplate]:
        return [
            cls.CodingAgent, cls.ComputerAgent, cls.ReviewerAgent, cls.ResearchAgent,
            cls.DocumentAgent, cls.VerifierAgent, cls.BrowserAgent, cls.DataAgent,
            cls.TerminalAgent, cls.FileAgent, cls.UniversalFileAgent, cls.EmailAgent,
            cls.CalendarAgent, cls.GitHubAgent
        ]

    @classmethod
    def get_template(cls, role_name: str) -> 'Optional[StaticAgentTemplate]':
        for t in cls.get_all():
            if t.template_id == role_name or t.role == role_name or t.__class__.__name__ == role_name or role_name in t.template_id:
                return t
            # Also checking if role_name perfectly matches the attribute name, e.g., "UniversalFileAgent"
        
        # Checking exact matches for class attributes
        if hasattr(cls, role_name):
            return getattr(cls, role_name)
            
        return None

StaticAgentTemplates = Templates
