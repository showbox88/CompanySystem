
import sys
import os
import json
from unittest.mock import MagicMock

# --- MOCK DEPENDENCIES BEFORE IMPORT ---
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.orm"] = MagicMock()
# Mock app.models (which imports sqlalchemy too)
mock_models = MagicMock()
sys.modules["app.models"] = mock_models
sys.modules["app.models.Agent"] = MagicMock()
sys.modules["app.models.AgentSkill"] = MagicMock()
sys.modules["app.models.Skill"] = MagicMock()

# Setup paths
sys.path.append(os.path.join(os.getcwd(), "backend"))

# NOW import the app modules
from app.skill_dispatcher import SkillDispatcher
from app.skills.registry import SkillRegistry
from app.skills import builtins # Register builtins

def test_dispatcher():
    print("--- Starting Skill Dispatcher Verification ---")
    
    # Mock DB and Agent
    mock_db = MagicMock()
    mock_agent = MagicMock()
    mock_agent.id = "test_agent"
    mock_agent.name = "TestAgent"
    
    # Subclass to bypass DB logic
    class TestDispatcher(SkillDispatcher):
        def _load_available_skills(self):
            skills = {}
            for name in ["image_generation", "read_file", "list_files"]:
                reg = SkillRegistry.get_skill(name)
                # Mock SQL Object
                skill_def = MagicMock()
                skill_def.name = name
                skill_def.description = reg["description"]
                skills[name] = {"definition": skill_def, "config": {}}
            return skills

    dispatcher = TestDispatcher(mock_db, mock_agent)
    
    test_cases = [
        (
            "Standard JSON", 
            '[[CALL_SKILL: image_generation | {"prompt": "A blue cat"}]]'
        ),
        (
            "JS Style Object (No Quotes)", 
            '[[CALL_SKILL: image_generation | {prompt: "A red dog"}]]'
        ),
        (
            "Colon Format (Colon Name)", 
            '[[CALL_SKILL: image_generation: prompt="A green bird"]]'
        ),
        (
            "Positional Argument (Quoted)", 
            '[[CALL_SKILL: image_generation("A yellow fish")]]'
        ),
        (
            "Positional Argument (Implicit Prompt)", 
            '[[CALL_SKILL: image_generation(A purple horse)]]'
        ),
        (
            "Fuzzy Name Match", 
            '[[CALL_SKILL: image_generation_v2("A fuzzy bear")]]'
        ),
        (
            "Read File (Positional)", 
            '[[CALL_SKILL: read_file("System/Company_Log.md")]]'
        )
    ]
    
    extra_config = {"api_key": "mock_key"}
    
    for title, input_text in test_cases:
        print(f"\nTesting: {title}")
        print(f"Input: {input_text}")
        result, executed = dispatcher.parse_and_execute(input_text, extra_config)
        print(f"Executed: {executed}")
        # Truncate result for readability
        safe_res = str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
        print(f"Result: {safe_res}")
        
        if "[ERROR" in str(result):
             print("❌ FAILED (Error in result)")
        elif not executed:
             print("❌ FAILED (Not Executed)")
        else:
             print("✅ PASSED")

if __name__ == "__main__":
    test_dispatcher()
