from typing import Dict, Any, Callable

class SkillRegistry:
    _skills: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def register(cls, name: str, display_name: str, description: str, parameters: Dict[str, Any]):
        def decorator(func: Callable):
            cls._skills[name] = {
                "name": name,
                "display_name": display_name,
                "description": description,
                "parameters": parameters,
                "handler": func
            }
            return func
        return decorator

    @classmethod
    def get_skill(cls, name: str):
        return cls._skills.get(name)

    @classmethod
    def get_all_skills(cls):
        return cls._skills
