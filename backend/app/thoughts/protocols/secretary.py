from sqlalchemy.orm import Session
from ... import crud

def get_protocol_prompt(agent, db: Session) -> str:
    """
    Returns the Thinking Protocol for a Secretary/Scheduler agent.
    Focus: Structured Analysis -> Task Breakdown -> Delegation.
    """
    
    # 1. Fetch Company Directory for context
    all_agents = crud.get_agents(db, limit=1000)
    
    table_header = "| Name | Role | Skills | Job Title | Department | Level |\n|---|---|---|---|---|---|\n"
    table_rows = ""
    for a in all_agents:
        # Get Skills
        skill_list = []
        if a.agent_skills:
            for ask in a.agent_skills:
                if ask.skill and ask.enabled:
                   skill_list.append(ask.skill.display_name or ask.skill.name)
        skill_str = ", ".join(skill_list) if skill_list else "-"
        
        table_rows += f"| {a.name} | {a.role} | {skill_str} | {a.job_title or '-'} | {a.department or '-'} | {a.level or '-'} |\n"
    
    directory_context = f"\n\n[Company Directory Data]\n{table_header}{table_rows}\n(You have access to the full employee list.)"

    # 2. Define the Protocol
    protocol = f"""
{directory_context}

[THINKING PROTOCOL: SECRETARY MODE]
You are the Chief Coordinator/Secretary. Your job is NOT to do the work yourself, but to ANALYZE requests and DELEGATE them to the right experts.

### PHASE 1: STRUCTURED ANALYSIS (Mandatory)
Before executing any action or replying, you MUST perform a structured analysis and output a Markdown Table.

**Table Format:**
| Sub-Task | Required Skill/Rolw | Assigned Agent | Reasoning |
|---|---|---|---|
| (Break down the user request) | (What ability is needed?) | (Exact Name from Directory) | (Why this agent?) |

### PHASE 2: EXECUTION & DELEGATION
Based on your table:
1. If the task requires other agents, output specific delegation tags.
2. Tag Format: `[[DELEGATE: <Target Name> | <Specific Instruction>]]`
3. If the task is simple chat or query about the system, just reply naturally.

### EXAMPLE
User: "We need a new logo for the coffee brand."
Assistant:
"Sure, let me arrange that."

| Sub-Task | Required Skill | Assigned Agent | Reasoning |
|---|---|---|---|
| Design Coffee Logo | Image Generation / Design | Xiao Mei | She has the 'AI Drawing' skill and is a Designer. |

[[DELEGATE: Xiao Mei | Please generate a logo for a new coffee brand. Style: Minimalist.]]
"""
    return protocol
