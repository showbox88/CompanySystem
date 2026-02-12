# Skill Library System Design (技能库系统设计)

## 1. Concept (概念)
Transform the system from purely "Text-Based Agents" to "Tool-Using Agents".
- **Skill (技能)**: A distinct capability (e.g., Image Generation, Web Search, Data Analysis).
- **Skill Library (技能库)**: A registry of all available skills.
- **Assignment (配置)**: Users can toggle skills on/off for each agent in the Agent Center.

## 2. Architecture (架构)

### A. Database (`models.py`)
New tables to manage skill assignments:
```python
class Skill(Base):
    __tablename__ = "skills"
    id = Column(String, primary_key=True)  # unique identifier, e.g. "image_gen"
    name = Column(String)  # display name
    description = Column(String)  # description for UI
    config = Column(JSON)  # default config

class AgentSkill(Base):
    __tablename__ = "agent_skills"
    agent_id = Column(String, ForeignKey("agents.id"), primary_key=True)
    skill_id = Column(String, ForeignKey("skills.id"), primary_key=True)
    config = Column(JSON) # User-specific config override
```

### B. Skill Registry (`backend/app/skills.py`)
A comprehensive registry that maps skill names to Python functions.
```python
SKILL_REGISTRY = {
    "image_generation": {
        "name": "Image Generation",
        "handler": generate_image, # python function
        "schema": {"prompt": "string"}
    }
}
```

### C. Execution Protocol (Tag-Based)
System Prompts will be automatically injected with available skills:
```text
[AVAILABLE SKILLS]
- image_generation: Generates images. Usage: [[CALL_SKILL: image_generation | {"prompt": "..."}]]
```

### D. Frontend (`frontend_app.py`)
- **Agent Center**: Add a "Skills" multiselect or checkbox list when editing agents.
- **Chat Interface**: Render the output of skills (e.g., display the generated image).

## 3. Implementation Steps (实施步骤)

1.  **Schema**: Update `models.py` (Add `AgentSkill`).
2.  **Backend**: Create `skills.py` with `ImageGeneration` logic.
3.  **Migration**: Update database (SQLite).
4.  **Logic**: Update `main.py` -> `call_llm_service` -> inject skills into prompt.
5.  **Logic**: Monitor output for `[[CALL_SKILL]]`, execute, and return result to LLM context (Function Calling loop) OR directly stream to user.
    - Simplified approach: Just execute and show result to user for now.
6.  **UI**: Skill selection during Agent Creation/Edit.
