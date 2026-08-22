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
        permission_scope=["filesystem.read", "filesystem.write", "test.run", "github.*"],
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
        role="Code and output review",
        permission_scope=["filesystem.read", "github.read"],
        default_system_prompt="You review work..."
    )
    
    ResearchAgent = StaticAgentTemplate(
        template_id="research_agent",
        role="Deep web and document research, cross-referencing, and synthesis",
        permission_scope=["browser.*", "search.web", "memory.semantic", "filesystem.read", "filesystem.write"],
        default_system_prompt="You are a researcher..."
    )
    
    DocumentAgent = StaticAgentTemplate(
        template_id="document_agent",
        role="Document reading and summarization",
        permission_scope=["filesystem.read"],
        default_system_prompt="You process documents..."
    )
    
    VerifierAgent = StaticAgentTemplate(
        template_id="verifier_agent",
        role="Task success verification",
        permission_scope=["filesystem.read", "test.run"],
        default_system_prompt="You verify completion..."
    )
    
    BrowserAgent = StaticAgentTemplate(
        template_id="browser_agent",
        role="Web navigation and extraction",
        permission_scope=["browser.*"],
        default_system_prompt="You operate a browser..."
    )
    
    DataAgent = StaticAgentTemplate(
        template_id="data_agent",
        role="Data analysis and transformation",
        permission_scope=["filesystem.read", "filesystem.write", "python.execute"],
        default_system_prompt="You analyze data..."
    )
    
    FileAgent = StaticAgentTemplate(
        template_id="file_agent",
        role="General file management",
        permission_scope=["filesystem.*"],
        default_system_prompt="You manage files..."
    )
    
    UniversalFileAgent = StaticAgentTemplate(
        template_id="universal_file_agent",
        role="Document/data file generation across formats",
        permission_scope=["filesystem.write", "filesystem.read"],  # Needs read to process source files
        default_system_prompt="You generate files in requested formats..."
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
            cls.FileAgent, cls.UniversalFileAgent, cls.EmailAgent, cls.CalendarAgent,
            cls.GitHubAgent
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
