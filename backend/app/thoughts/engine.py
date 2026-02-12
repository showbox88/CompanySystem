from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from ..models import Agent
from .protocols import secretary

class ThinkingEngine:
    """
    Central engine for determining an agent's 'Thinking Mode' and injecting 
    corresponding system prompts (cognitive protocols).
    """

    @staticmethod
    def enrich_system_prompt(agent: Agent, db: Session, context: Dict[str, Any] = None) -> str:
        """
        Analyze the agent and return prompt additions based on their role/mode.
        """
        prompt_additions = ""
        
        # 1. Secretary / Scheduler Mode
        # Heuristic: Check role for "Assistant", "Secretary", "助理", "秘书"
        role_lower = (agent.role or "").lower()
        title_lower = (agent.job_title or "").lower()
        
        is_secretary = (
            "assistant" in role_lower or 
            "secretary" in role_lower or 
            "助理" in role_lower or 
            "秘书" in role_lower
        )

        if is_secretary:
            prompt_additions += secretary.get_protocol_prompt(agent, db)

        # Future: Add other modes like 'Coder', 'Architect', etc.
        
        return prompt_additions
