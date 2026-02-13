
import re
import json
from sqlalchemy.orm import Session
from .models import Agent, AgentSkill, Skill
from .skills import SkillRegistry

class SkillDispatcher:
    def __init__(self, db: Session, agent: Agent):
        self.db = db
        self.agent = agent
        self.available_skills = self._load_available_skills()

    def _load_available_skills(self):
        """
        Load enabled skills for this agent.
        """
        # Join AgentSkill and Skill
        results = self.db.query(AgentSkill, Skill).\
            join(Skill, AgentSkill.skill_id == Skill.id).\
            filter(AgentSkill.agent_id == self.agent.id).\
            filter(AgentSkill.enabled == 1).\
            all()
        
        skills = {}
        for askill, skill in results:
            # Merge global config with agent override
            # registry_entry = SkillRegistry.get_skill(skill.name)
            skills[skill.name] = {
                "definition": skill,
                "config": askill.config or {}
            }
        return skills

    def get_system_prompt_addition(self) -> str:
        """
        Generate the [AVAILABLE SKILLS] section for the System Prompt.
        """
        if not self.available_skills:
            return ""

        prompt = "\n\n[AVAILABLE SKILLS]\n"
        prompt += "You have access to the following skills. To use one, output the specific tag.\n"
        
        for name, data in self.available_skills.items():
            skill_def = data['definition']
            # Get parameters from registry for accurate instruction
            reg_entry = SkillRegistry.get_skill(name)
            params = reg_entry['parameters'] if reg_entry else {}
            
            prompt += f"- {name}: {skill_def.description}\n"
            prompt += f"  Usage: [[CALL_SKILL: {name} | {{JSON Arguments}}]]\n"
            # prompt += f"  Schema: {json.dumps(params)}\n"
        
        prompt += "\n[SKILL EXECUTION RULES]\n"
        prompt += "1. Output the [[CALL_SKILL]] tag on a new line.\n"
        prompt += "2. The system will intercept this tag, execute the code, and return the result.\n"
        prompt += "3. DO NOT hallucinate the result. Wait for the system response.\n"
        
        return prompt

    def parse_and_execute(self, text: str, global_config: dict) -> tuple[str, bool]:
        """
        Parses text for [[CALL_SKILL:...]] tags and executes them.
        Returns: 
            (result_text, executed_flag)
        """
        # Regex to capture [[CALL_SKILL: name | {args}]]
        # Handle potential newlines in JSON args
        # Regex to capture [[CALL_SKILL: ...]]
        # 1. Standard: [[CALL_SKILL: name | {json}]]
        # 2. Pythonic: [[CALL_SKILL: name(arg="val", ...)]]
        
        # Primary Regex (Capture the whole content after CALL_SKILL:)
        pattern = r"\[\[CALL_SKILL:\s*(.*?)\]\]"
        match = re.search(pattern, text, re.DOTALL)
        
        if not match:
            return text, False

        content = match.group(1).strip()
        print(f"DEBUG: Skill Dispatcher Raw Content: [{content}]")
        
        # Determine format
        if "|" in content:
            # Format: name | {json}
            parts = content.split("|", 1)
            skill_name = parts[0].strip()
            args_str = parts[1].strip()
            args = self._parse_json_safe(args_str)
            if args is None: # _parse_json_safe returns {} on failure, but let's check if it returns valid dict
                 return f"[ERROR: Invalid JSON arguments for skill '{skill_name}'.]", True
        else:
            # Format: name(args)
            # Simple parser for name(key="value", ...)
            # Extract name
            match_func = re.match(r"([a-zA-Z0-9_]+)\s*\((.*)\)", content, re.DOTALL)
            match_json_no_pipe = re.match(r"([a-zA-Z0-9_]+)\s*(\{.*\})", content, re.DOTALL)
            # Catch-all: Name followed by optional colon/space and then args
            # Matches: "skill_name: args" or "skill_name args"
            match_catchall = re.match(r"([a-zA-Z0-9_]+)(?:[:\s]+)(.*)", content, re.DOTALL)
            
            if match_func:
                skill_name = match_func.group(1).strip()
                args_content = match_func.group(2).strip()
                args = self._parse_key_value(args_content)
                
                # FALLBACK: If no key-value pairs found, treating as a single positional argument
                if not args and args_content:
                    # Try to strip quotes
                    cleaned_arg = args_content.strip()
                    if (cleaned_arg.startswith('"') and cleaned_arg.endswith('"')) or \
                       (cleaned_arg.startswith("'") and cleaned_arg.endswith("'")):
                        cleaned_arg = cleaned_arg[1:-1]
                    
                    # Fetch skill definition to find the default parameter
                    reg_entry = SkillRegistry.get_skill(skill_name)
                    if reg_entry:
                        params = reg_entry.get("parameters", {})
                        required = params.get("required", [])
                        if required and len(required) > 0:
                            # Assign to the first required parameter
                            primary_key = required[0]
                            args = {primary_key: cleaned_arg}
                            print(f"DEBUG: Auto-mapped positional arg to '{primary_key}': {cleaned_arg}")

            elif match_json_no_pipe:
                 # Format: name {json} (Missing pipe)
                 skill_name = match_json_no_pipe.group(1).strip()
                 args_str = match_json_no_pipe.group(2).strip()
                 args = self._parse_json_safe(args_str)
                 
                 # FALLBACK: If JSON parsing failed (empty args), try parsing inner content as key-value pairs
                 # (Handles JS-style objects like {key: "val"})
                 if not args and args_str.startswith("{") and args_str.endswith("}"):
                     inner_content = args_str[1:-1]
                     print(f"DEBUG: JSON failed, trying key-value parse on: {inner_content}")
                     args = self._parse_key_value(inner_content)

            elif match_catchall:
                 # Fallback: Try to parse key="val" from whatever is left
                 skill_name = match_catchall.group(1).strip()
                 args_content = match_catchall.group(2).strip()
                 # Try valid JSON first
                 if args_content.startswith("{") and args_content.endswith("}"):
                     args = self._parse_json_safe(args_content)
                 else:
                     args = self._parse_key_value(args_content)
            else:
                 # Fallback: maybe just name?
                 skill_name = content.strip()
                 args = {}

        # Verify skill is available
        if skill_name not in self.available_skills:
             # FUZZY MATCH: Check if it's a hallucinated variant (e.g. image_generation_v2 -> image_generation)
             found_fuzzy = False
             for avail_name in self.available_skills.keys():
                 if skill_name.startswith(avail_name) or avail_name in skill_name:
                     print(f"DEBUG: Fuzzy matched '{skill_name}' to '{avail_name}'")
                     skill_name = avail_name
                     found_fuzzy = True
                     break
            
             if not found_fuzzy:
                 return f"[ERROR: Skill '{skill_name}' is not enabled for this agent. Content: {content}]", True

        # Get Handler
        reg_entry = SkillRegistry.get_skill(skill_name)
        if not reg_entry:
            return f"[ERROR: Skill implementation for '{skill_name}' not found in registry.]", True
        
        handler = reg_entry['handler']
        
        # Prepare Config
        merged_config = global_config.copy()
        
        # Inject Agent Identity for file saving
        merged_config['agent_name'] = self.agent.name
        merged_config['agent_provider'] = getattr(self.agent, 'provider', 'openai')
        
        # Inject Gemini Key if available (it might be in global_config, but let's ensure it's accessible)
        # global_config in main.py usually comes from get_llm_config which HAS gemini_api_key.
        # So we just rely on global_config having it.

        
        agent_skill_config = self.available_skills[skill_name]['config']
        if agent_skill_config:
            merged_config.update(agent_skill_config)
            
        # Execute
        try:
            print(f"Executing Skill: {skill_name} with args: {args}")
            # Ensure args match requirements (simple check?)
            result = handler(merged_config, args)
            return result, True
        except Exception as e:
            return f"[ERROR: Skill execution failed: {str(e)}]", True

    def _parse_key_value(self, text):
        args = {}
        # Regex for key="value" or key='value' or key=123
        # Supports both = and : as separators
        arg_pattern = r'(\w+)\s*[=:]\s*(?:"([^"]*)"|\'([^\']*)\'|([0-9.]+))'
        for arg_match in re.finditer(arg_pattern, text):
            key = arg_match.group(1)
            val = arg_match.group(2) or arg_match.group(3) or arg_match.group(4)
            args[key] = val
        return args

    def _parse_json_safe(self, text):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                import ast
                return ast.literal_eval(text)
            except:
                return {} # Failed

