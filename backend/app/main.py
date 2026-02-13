from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
import time
import os
from datetime import datetime
import traceback
import openai
from .database import engine, Base, get_db, SessionLocal
from .models import Agent, Task
from .workflows.registry import get_workflow, get_all_workflows_prompt
from . import project_manager
from . import models, schemas, crud
# Force load skills
from . import skills

# Create tables
# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Company AI System")

@app.on_event("startup")
def startup_event():
    # Sync Skills from Registry to DB
    from .skills.registry import SkillRegistry
    db = SessionLocal()
    try:
        registered_skills = SkillRegistry.get_all_skills()
        print(f"Syncing {len(registered_skills)} skills to DB...")
        crud.sync_skills(db, registered_skills)
        print("Skill Sync Complete.")
    finally:
        db.close()

# --- LLM Service ---
def get_llm_config(db: Session):
    api_key = crud.get_setting(db, "api_key")
    base_url = crud.get_setting(db, "base_url")
    return {
        "api_key": api_key.value if api_key else None,
        "base_url": base_url.value if base_url else "https://api.openai.com/v1"
    }

def call_llm_service(agent: models.Agent, prompt: str, config: dict, stream: bool = False, db: Session = None, history: List[schemas.ChatMessage] = [], task_mode: str = "chat"):
    api_key = config.get("api_key")
    base_url = config.get("base_url", "https://api.openai.com/v1")
    import requests
    import json
    
    # Construct URL
    base_url = base_url.rstrip('/')
    if not base_url.endswith("/chat/completions"):
        api_url = f"{base_url}/chat/completions"
    else:
        api_url = base_url
        
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json"
    }
    
    # Construct Identity Context
    identity_prompt = (
        f"You are {agent.name}.\n"
        f"Role: {agent.role}\n"
        f"Job Title: {agent.job_title or 'N/A'}\n"
        f"Department: {agent.department or 'N/A'}\n"
        f"Level: {agent.level or 'N/A'}\n\n"
        f"{agent.system_prompt}"
    )

    # Inject Company Logs for ALL Agents (Shared Awareness)
    # Previously restricted to Secretary/Assistant, now broadened so everyone knows about new files
    # Inject Company Logs for ALL Agents (Shared Awareness)
    # Inject Company Logs for ALL Agents (Shared Awareness)
    # READ DIRECTLY FROM MARKDOWN FILE (Source of Truth)
    # backend/app/main.py -> backend/app -> backend -> CompanySystem
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    LOG_FILE = os.path.join(BASE_DIR, "Company Doc", "System", "Company_Log.md")
    
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                # Get last 50 lines to ensure visibility of recent context
                recent_lines = lines[-50:]
                log_text = "".join(recent_lines)
                identity_prompt += f"\n\n[Recent Company System Activity]\n{log_text}\n(Use this to be aware of recently created files by other agents.)"
        except Exception as e:
            print(f"Failed to read log file: {e}")
    
    # 2. Add Delegation Instruction for Secretary (Only in Chat Mode)
    if task_mode == "chat" and ("secretary" in agent.role.lower() or "秘书" in agent.role.lower() or "secretary" in (agent.job_title or "").lower()):
        # Inject Company Directory so Secretary knows who to delegate to
        all_agents = crud.get_agents(db, limit=1000)
        table_header = "| Name | Role | Job Title | Department | Level |\n|---|---|---|---|---|\n"
        table_rows = ""
        for a in all_agents:
            table_rows += f"| {a.name} | {a.role} | {a.job_title or '-'} | {a.department or '-'} | {a.level or '-'} |\n"
        
        identity_prompt += (
            f"\n\n[Company Directory Data]\n{table_header}{table_rows}\n(You have access to the full employee list.)"
            f"\n\n{get_all_workflows_prompt()}"
            "\n\n[INSTRUCTION: COMMAND ANALYSIS PROTOCOL]\n"
            "You are a Scheduler/Dispatcher. To ensure accuracy, you MUST follow this 2-step process for EVERY user message:\n"
            "\n"
            "### STEP 1: ANALYZE (Mental Sandbox)\n"
            "Before deciding to delegate or answer, output a Markdown table analyzing the request:\n"
            "| Field | Value |\n"
            "|---|---|\n"
            "| **User Intent** | (QUERY / COMMAND / CHAT / PROJECT_PLAN) |\n"
            "| **Key Entities** | (Who is mentioned?) |\n"
            "| **Command Type** | (e.g. Write File, Answer Question, Assign Task, Plan Project) |\n"
            "| **Workflow ID** | (Select best fit from AVAILABLE WORKFLOWS, default 'general_task') |\n"
            "| **Valid Target?** | (Check Directory Pattern Matching: Yes/No) |\n"
            "\n"
            "### STEP 2: ACT\n"
            "Based on the table above:\n"
            "1. **IF INTENT = QUERY/CHAT** -> Answer directly.\n"
            "2. **IF INTENT = PROJECT_PLAN (Complex/Sequential Goal)**:\n"
            "   - TRIGGER: User uses words like 'First... Then...', 'After...', 'Based on...', '先...后...', '然后...'\n"
            "   - TRIGGER: Tasks have dependencies (Task B needs Task A's output).\n"
            "   - Break down the goal into a sequential checklist.\n"
            "   - OUTPUT: [[CREATE_PROJECT: {Title} | {Step 1} | {Step 2} ...]]\n"
            "   - STEP FORMAT: 'AgentName: Instruction' (e.g. 'Xiao Zhang: Write script')\n"
            "   - EXAMPLE: [[CREATE_PROJECT: SciFi_Comic | Xiao Zhang: Write script | Xiao Mei: Draw content based on script]]\n"
            "3. **IF INTENT = COMMAND (Single/Parallel Task)**:\n"
            "   - TRIGGER: Independent tasks that can run at the same time.\n"
            "   - Identify ALL targets.\n"
            "   - Identify ALL targets.\n"
            "   - **CRITICAL**: The Target Name MUST match the 'Name' column in the [Company Directory Data] EXACTLY.\n"
            "   - DO NOT translate names (e.g. if directory says '小张', DO NOT output 'Xiao Zhang').\n"
            "   - **CRITICAL**: DO NOT TRANSLATE THE INSTRUCTION.\n"
            "   - OUTPUT THE DELEGATION TAGS, ONE PER LINE.\n"
            "   - TAG FORMAT: [[DELEGATE: {Exact Target Name} | {Workflow ID} | {Original Instruction}]]\n"
            "   - EXAMPLE: \n"
            "     [[DELEGATE: 小张 | content_creation | 写一份日报]]\n"
            "     [[DELEGATE: 小美 | visual_design | Draw a sci-fi bike]]\n"
        )
    # Inject Thinking Protocol (Cognitive Architecture)
    from .thoughts.engine import ThinkingEngine
    identity_prompt += ThinkingEngine.enrich_system_prompt(agent, db, context={"task_mode": task_mode})

    # 3. Task Mode Instructions

    # 3. Task Mode Instructions
    
    
    if task_mode == "background_worker":
        # BACKGROUND WORKER MODE (Multi-Turn Reasoning)
        identity_prompt += (
            f"\n\n[INSTRUCTION: BACKGROUND TASK EXECUTION]\n"
            "ROLE: You are an autonomous Task Executor. You DO NOT chat. You ONLY execute skills.\n"
            "OBJECTIVE: Produce the final output file requested by the user.\n"
            "\n"
            "!!! CRITICAL RULES !!!\n"
            "1. IF you need information (e.g. description, content) -> CALL 'read_file'.\n"
            "2. IF you need to generate media -> CALL 'image_generation'.\n"
            "3. IF you have the results -> Output the final file content directly.\n"
            "4. NEVER ask the user for clarification. GUESS based on [Recent Company System Activity] or [Context Hints].\n"
            "\n"
            "EXAMPLES:\n"
            "User: 'Draw a bike based on Xiao Zhang'\n"
            "You: [[CALL_SKILL: read_file | {'file_path': 'Xiao Zhang/Bike_Description.md'}]]\n"
            "\n"
            "User: 'Generate image from prompt'\n"
            "You (finding 'Prompt_123.md' in logs): [[CALL_SKILL: read_file | {'file_path': 'Prompt_123.md'}]]\n"
            "\n"
            "ACTION REQUIRED: Output a [[CALL_SKILL]] tag NOW.\n"
        )
    
    if task_mode == "file_generation":
        # Force Generation of FILE CONTENT
        identity_prompt += (
            "\n\n[SYSTEM OVERRIDE: CONTENT GENERATION]\n"
            "You are a dedicated file content generator.\n"
            f"REQUIRED IDENTITY: Name='{agent.name}', Role='{agent.role}', Department='{agent.department or 'N/A'}'\n"
            "1. DO NOT ask for confirmation. The user has ALREADY confirmed.\n"
            "2. DO NOT output tags like [[EXECUTE_TASK]].\n"
            "   - EXCEPTION: You MAY use [[CALL_SKILL: ...]] tags if you need to generate images or search data.\n"
            "3. DO NOT chat or explain.\n"
            "4. OUTPUT DIRECTLY THE CONTENT of the requested file.\n"
            "5. CONTENT GUIDELINES: \n"
            "   - **LANGUAGE PRIORITY**: Use the SAME LANGUAGE as the prompt/instruction. (Chinese -> Chinese)\n"
            "   - IF DETAILS ARE MISSING: Invent plausible professional data matching YOUR IDENTITY (Name/Role) above.\n"
            "   - **IMAGES**: If the task involves DESIGN/DRAWING, you MUST use the [[CALL_SKILL: image_generation...]] tag in the file content.\n"
            "   - **EXTERNAL FILES**: If the task refers to another agent's output (e.g. 'Xiao Zhang's file'), you MUST:\n"
            "       1. CHECK THE LOGS below for files created by **THAT AGENT** (e.g. Look for 'Created by (Xiao Zhang)').\n"
            "       2. **IGNORE** files created by YOU ({agent.name}). Do not read your own output files!\n"
            "       3. **MATCH INTENT**: If looking for a 'Description', look for files named 'Description', 'Requirements', or Chinese equivalents like '产品描述', '需求文档'.\n"
            "       4. Use [[CALL_SKILL: read_file...]] to get the content.\n"
            "       5. DO NOT ask the user for the file. FIND IT YOURSELF.\n"
            "   - NEVER invent a different name for yourself.\n"
            "   - NEVER invent a different name for yourself.\n"
        )
    else: # Default: "chat"
        identity_prompt += (
            "\n\n[INSTRUCTION: FILE GENERATION / TASK EXECUTION]\n"
            "- If user asks to JUST SEE/VIEW info, display it in chat.\n"
            "- If user asks to GENERATE A FILE/REPORT:\n"
            "  1. If the user HAS NOT confirmed yet, ASK FOR CONFIRMATION (e.g. 'Ready to generate, proceed?').\n"
            "     - **LANGUAGE**: Ask in the SAME LANGUAGE as the user (e.g. User: Chinese -> You: '准备生成文件，是否继续？').\n"
            "  2. If the user EXPLICITLY CONFIRMS (e.g. 'Yes', 'Confirm', 'Generate it'), YOU MUST OUTPUT THE TAG BELOW.\n"
            "  3. TAG FORMAT: [[EXECUTE_TASK: {Task Title} | {Detailed Instruction}]]\n"
            "  4. CRITICAL: Do not output the content of the file yourself. OUTPUT ONLY THE TAG to trigger generation."
        )

    # Build messages
    if task_mode == "dispatch":
        # DISPATCH MODE: Ignore history, Force Execution
        # We need to be very aggressive here.
        messages = [{"role": "system", "content": identity_prompt}]
        
        force_msg = (
            f"Subject: {prompt}\n\n"
            "COMMAND: Generate the [[EXECUTE_TASK]] tag for the above subject immediately.\n"
            "CONSTRAINT: Do not chat. Do not ask questions. Output the tag ONLY."
        )
        messages.append({"role": "user", "content": force_msg})
        
    else:
        # NORMAL CHAT / FILE GEN MODE
        messages = [{"role": "system", "content": identity_prompt}]
        
        # Add history
        for msg in history:
            # Handle both Pydantic models (msg.role) and Dicts (msg['role'])
            if isinstance(msg, dict):
                role_val = msg.get("role")
                content_val = msg.get("content")
            else:
                role_val = msg.role
                content_val = msg.content
                
            if not content_val or not str(content_val).strip():
                continue # Skip empty messages
                
            role = "assistant" if role_val == "assistant" else "user"
            messages.append({"role": role, "content": content_val})

        # Add current message
        if prompt and str(prompt).strip():
            messages.append({"role": "user", "content": prompt})
        else:
            print("WARNING: call_llm_service received empty prompt. Using placeholder.")
            messages.append({"role": "user", "content": "Proceed."})

    payload = {
        "model": agent.model_name,
        "messages": messages,
        "temperature": agent.temperature,
        "stream": stream
    }
    
    # Make direct HTTP request to avoid library conflicts
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=120, stream=stream)
        
        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}: {response.text}")
            
        if stream:
            return response
        else:
            result = response.json()
            return result['choices'][0]['message']['content']
    except Exception as e:
        raise Exception(f"LLM Call Failed: {str(e)}")

def process_task_background(task_id: str):
    # Create new DB Session for this thread
    db = SessionLocal()
    try:
        # 1. Get Task and Agent
        task = db.query(models.Task).filter(models.Task.id == task_id).first()
        if not task:
            return
        agent = task.agent

        # 2. Get LLM Config
        config = get_llm_config(db)
        if not config["api_key"]:
            crud.update_task_status(db, task_id, models.TaskStatus.FAILED, output="Error: API Key not configured.")
            return

        # 3. Update Status to Running
        task.status = models.TaskStatus.RUNNING.value
        db.commit()

        # 4. Agent Loop (Think - Act - Observe - Act)
        match_limit = 5 # Avoid infinite loops
        final_content = ""
        
        # Initial Message History for this task
        # We need to maintain a local history for this multi-step process
        
        # [WORKFLOW DETECTION]
        # Check if the prompt has [WORKFLOW: xxx]
        workflow_data = None
        import re
        wf_match = re.match(r"\[WORKFLOW:\s*(.*?)\]", task.input_prompt)
        if wf_match:
            wf_id = wf_match.group(1).strip()
            workflow_data = get_workflow(wf_id)
            print(f"DEBUG: Task assigned Workflow: {wf_id}")
        else:
            # Default to General Task
            workflow_data = get_workflow("general_task")
            
        # Format SOP Steps
        sop_text = "\n".join(workflow_data['steps'])
        
        # Inject SOP into System Prompt (Override/Append)
        agent_system_prompt = agent.system_prompt + f"\n\n[ASSIGNED PROTOCOL: {workflow_data['name']}]\nDESCRIPTION: {workflow_data['description']}\nSTEPS:\n{sop_text}\n\n[INSTRUCTION]\nStrictly follow the STEPS above. Process one step at a time if needed.\n\n[CRITICAL OUTPUT FORMAT]\nThis task is for file generation. Your output will be saved DIRECTLY to a file.\n1. DO NOT output your internal thought process, analysis, or 'Step 1...' headers.\n2. DO NOT include conversational filler like 'Here is the story:'.\n3. OUTPUT ONLY THE FINAL RESULT CONTENT.\n4. DO NOT ASK FOR CONFIRMATION. YOU HAVE FULL PERMISSION. EXECUTE IMMEDIATELY."
        
        system_msg = {"role": "system", "content": agent_system_prompt} 
        
        # Re-construct the full identity prompt (similar to call_llm_service logic)
        # To avoid duplicating code, we might need to refactor call_llm_service to simply take messages? 
        # For now, let's rely on call_llm_service's ability to handle the "first" call, and then we manually handle subsequent calls?
        # Actually, call_llm_service currently constructs the system prompt internally every time.
        # So we need to PASS this new `agent_system_prompt` to call_llm_service.
        # But call_llm_service takes `Agent` object and reads `agent.system_prompt`.
        # HACK: Temporarily modify the agent object instance (not DB) for this call?
        agent.system_prompt = agent_system_prompt # This modifies the ORM object in memory for this session
        
        task_history = [] 
        
        # [CONTEXT HINT INJECTION]
        # To help the agent find relevant files (since System Prompt might be ignored),
        # we parse the recent logs and append potential file candidates to the USER PROMPT.
        try:
            BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            LOG_FILE = os.path.join(BASE_DIR, "Company Doc", "System", "Company_Log.md")
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    # Look for [FILE_CREATED] in last 30 lines
                    recent_files = []
                    seen_files = set()
                    for line in lines[-30:]:
                        if "[FILE_CREATED]" in line:
                            # Parse: - **[Time]** [FILE_CREATED] (AgentName): Created file: Filename ...
                            # 1. Extract Agent Name
                            try:
                                author = line.split("(")[1].split(")")[0].strip()
                            except:
                                author = "Unknown"
                                
                            # 2. Skip if author is me (Prevent Self-Reading Loop)
                            print(f"DEBUG: Checking File Log - Author: '{author}' vs Agent: '{agent.name}'")
                            if author == agent.name:
                                continue
                                
                            # 3. Extract Filename
                            parts = line.split("Created file: ")
                            if len(parts) > 1:
                                fname = parts[1].split(" ")[0].strip()
                                if fname not in seen_files:
                                    recent_files.append(f"[{author}] {fname}")
                                    seen_files.add(fname)
                    
                    if recent_files:
                        hint_msg = "\n\n[System Context Hint: POTENTIAL TARGET FILES (Use 'read_file' on one of these)]:\n"
                        for rf in recent_files:
                            hint_msg += f"- {rf}\n"
                        hint_msg += "(System detected these recent files. You MUST read the most relevant one to proceed.)"
                        
                    if recent_files:
                        hint_msg = "\n\n[System Context Hint: POTENTIAL TARGET FILES]\n"
                        for rf in recent_files:
                            hint_msg += f"- {rf}\n"
                        hint_msg += "(Note: These files were recently created by others. Use them ONLY if your task requires it. Otherwise, ignore them.)"
                        
                        # [SMART CONTEXT] Auto-read the file if the prompt mentions the author
                        # e.g. "based on the story written by Xiao Zhang" -> Find Xiao Zhang's file and read it.
                        prompt_lower = task.input_prompt.lower()
                        for rf in recent_files:
                            # rf format: "[Author] Filename"
                            try:
                                r_author = rf.split("]")[0].replace("[", "").strip()
                                r_fname = rf.split("]")[1].strip()
                                
                                # Check if author name is in prompt (e.g. "based on Xiao Zhang")
                                # Simple partial match
                                if r_author.lower() in prompt_lower:
                                    print(f"DEBUG: Smart Context - Start reading '{r_fname}' for instruction '{task.input_prompt[:20]}...'")
                                    
                                    # Locate the file
                                    # We need to find where it lives.
                                    # We know the structure: Company Doc/{Author}/{Filename}
                                    # But Agent Name might be normalized.
                                    # Let's search recursively or guess.
                                    
                                    # Try Guessing
                                    # Need a helper to find file by name in Company Doc
                                    potential_path = os.path.join(BASE_DIR, "Company Doc", r_author, r_fname)
                                    if not os.path.exists(potential_path):
                                         # Search
                                         for root, dirs, files in os.walk(os.path.join(BASE_DIR, "Company Doc")):
                                             if r_fname in files:
                                                 potential_path = os.path.join(root, r_fname)
                                                 break
                                    
                                    if os.path.exists(potential_path):
                                        with open(potential_path, "r", encoding="utf-8") as pf:
                                            f_content = pf.read()
                                            hint_msg += f"\n\n[AUTO-READ CONTENT of '{r_fname}']:\n{f_content[:2000]}\n...(content truncated if too long)..."
                                            print(f"DEBUG: Auto-read {len(f_content)} bytes.")
                            except Exception as e:
                                print(f"DEBUG: Smart Context Error: {e}")

                        # [PROJECT CONTEXT FALLBACK]
                        # If we are in a PROJECT, and no specific file has been auto-read yet,
                        # assume the MOST RECENT file from ANYONE ELSE is the input for this step.
                        # (Sequential workflow assumption)
                        if task.project_file and "[AUTO-READ CONTENT" not in hint_msg and recent_files:
                            print("DEBUG: Project Context Fallback - Auto-reading the most recent file.")
                            try:
                                # recent_files is sorted by time (lines read from log bottom-up? wait, log lines are chronological)
                                # We iterated `lines[-30:]`. So the last item in `recent_files` is the most recent.
                                # recent_files append order: chronological (lines read sequentially)
                                last_file_entry = recent_files[-1] 
                                # entry format: "[Author] Filename"
                                
                                lf_author = last_file_entry.split("]")[0].replace("[", "").strip()
                                lf_fname = last_file_entry.split("]")[1].strip()
                                
                                # Find path
                                potential_path = os.path.join(BASE_DIR, "Company Doc", lf_author, lf_fname)
                                if not os.path.exists(potential_path):
                                     for root, dirs, files in os.walk(os.path.join(BASE_DIR, "Company Doc")):
                                         if lf_fname in files:
                                             potential_path = os.path.join(root, lf_fname)
                                             break
                                             
                                if os.path.exists(potential_path):
                                    with open(potential_path, "r", encoding="utf-8") as pf:
                                        f_content = pf.read()
                                        hint_msg += f"\n\n[PROJECT CONTEXT: Auto-read '{lf_fname}' by {lf_author}]:\n{f_content[:2000]}\n...(content truncated)..."
                            except Exception as e:
                                print(f"DEBUG: Project Context Fallback Failed: {e}")
                                
                    else:
                        hint_msg = ""
                        
        except Exception as e:
            print(f"DEBUG: Failed to inject context hint: {e}")
            hint_msg = ""
            
        generated_image_files = []
        last_skill_call = None
        total_skills_executed = 0
        
        for turn in range(match_limit):
            print(f"DEBUG: Background Task Turn {turn+1}. Prompt: {task.input_prompt[:50]}...")
            
            # Construct Effective Prompt
            effective_prompt = ""
            if turn == 0:
                # Turn 0: Instruction + Hint
                effective_prompt = f"[PRIMARY INSTRUCTION]\n{task.input_prompt}\n[/PRIMARY INSTRUCTION]"
                if hint_msg:
                    effective_prompt += f"\n\n{hint_msg}"
            else:
                # Subsequent turns
                effective_prompt = "Continue/Result: ..."
            
            response_text = call_llm_service(
                agent, 
                effective_prompt, 
                config, 
                db=db, 
                task_mode="background_worker",
                history=task_history
            )
            
            # Check for External System Errors
            if "[SYSTEM ERROR]" in response_text and "No previous valid input" in response_text:
                print(f"CRITICAL ERROR FROM LLM: {response_text}")
                # Retry if turn 0
                if turn == 0:
                    print("Retrying Turn 0 with re-phrased prompt...")
                    current_prompt = "Execute this task: " + task.input_prompt
                    response_text = call_llm_service(agent, current_prompt, config, db=db, task_mode="background_worker", history=[])
                else:
                    pass

            # Check for Skills
            from .skill_dispatcher import SkillDispatcher
            dispatcher = SkillDispatcher(db, agent)
            
            result_text = response_text
            executed_any = False
            
            # Parse ALL tags in this response
            import re
            while True:
                match = re.search(r"\[\[CALL_SKILL:\s*(.*?)\]\]", result_text, re.DOTALL)
                if not match:
                    break
                
                tag_string = match.group(0)
                print(f"DEBUG: Found tag: {tag_string}")
                
                skill_result, executed = dispatcher.parse_and_execute(tag_string, config)
                
                executed_any = True
                
                # [LOOP PREVENTION]
                current_skill_signature = tag_string
                if current_skill_signature == last_skill_call:
                    print(f"DEBUG: Detected Repetitive Skill Call '{tag_string}'. Aborting Loop.")
                    
                    # specific guidance
                    advice = "You are repeating yourself. Stopping execution."
                    if "read_file" in tag_string:
                        advice = "You have already read this file. The content is visible in the history above. DO NOT READ IT AGAIN. Proceed immediately to the next step (e.g., generate image or write content)."
                    elif "image_generation" in tag_string:
                        advice = "You have already generated the image. The system has captured it. DO NOT GENERATE AGAIN. Output the final response now."
                    
                    task_history.append({"role": "user", "content": f"[SYSTEM]: {advice}"})
                    break 
                last_skill_call = current_skill_signature

                # [IMAGE OUTPUT CAPTURE]
                skill_res_str = str(skill_result)
                
                # DEBUG LOGGING
                print(f"DEBUG: Skill Execution Result: {skill_res_str}")
                try:
                    crud.create_log(db, "SKILL_DEBUG", f"Agent {agent.name} executed {tag_string}. Result: {skill_res_str[:200]}...", agent_id=agent.id)
                except:
                    pass

                if "image_generation" in tag_string:
                    # 1. Check for explicit path format "Image generated at: ..."
                    if "Image generated at" in skill_res_str:
                        try:
                            img_path = skill_res_str.split(": ")[1].strip()
                            generated_image_files.append(img_path)
                            print(f"DEBUG: Captured Image (Explicit): {img_path}")
                        except:
                            pass
                    # 2. Check for Markdown format "![...](path)"
                    else:
                        match_md = re.search(r"!\[.*?\]\((.*?)\)", skill_res_str)
                        if match_md:
                            img_path = match_md.group(1).strip()
                            # If path is URL, we might exclude it if we only want local files?
                            # But builtins.py returns "assets/img.png" for local files.
                            if "assets/" in img_path:
                                generated_image_files.append(img_path)
                                print(f"DEBUG: Captured Image (Markdown): {img_path}")
                
                # Add to history
                task_history.append({"role": "assistant", "content": tag_string})
                task_history.append({"role": "user", "content": f"System Output: {skill_result}"})
                
                break 
            
            if executed_any:
                total_skills_executed += 1
                continue 
            else:
                # No skills called. Check for content.
                # RELAXED RULE: If we have executed AT LEAST ONE skill previously (e.g. read file, generated image),
                # we accept "Done" or short responses as final.
                
                is_short_response = len(response_text.strip()) < 50
                has_done_work = total_skills_executed > 0
                
                if turn < 2 and not has_done_work and is_short_response and "[[CALL_SKILL" not in response_text:
                     print(f"DEBUG: No skill triggered in Turn {turn+1} AND content too short AND no prior work. Forcing retry.")
                     task_history.append({"role": "assistant", "content": response_text})
                     task_history.append({"role": "user", "content": "[SYSTEM ERROR]: You failed to take action. You are a Background Worker. You MUST using a [[CALL_SKILL]] tag to proceed. Do not just talk. Execute now."})
                     continue
                
                # Otherwise, accept as final content
                print(f"DEBUG: No skills triggered. Final Response: {result_text[:100]}...")
                final_content = response_text
                break
        
        # [FINAL CONTENT ASSEMBLER]
        if generated_image_files:
            if not final_content: 
                final_content = "### Generated Assets\n"
            else:
                final_content += "\n\n### Generated Assets\n"
                
            for img in generated_image_files:
                final_content += f"![Generated Image]({img})\n"
                
        generated_content = final_content if final_content else "No content generated."
             
        # 5. Save to File
        # ... (rest of saving logic)
        
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        agent_name_clean = "".join([c for c in agent.name if c.isalnum() or c in (' ', '-', '_', '(', ')')]).strip()
        OUTPUT_DIR = os.path.join(BASE_DIR, "Company Doc", agent_name_clean)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        timestamp = int(time.time())
        clean_title = "".join([c for c in task.title if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        file_name = f"{clean_title}_{task_id[:8]}.md"
        file_path = os.path.join(OUTPUT_DIR, file_name)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(generated_content)
            
        crud.update_task_status(
            db, 
            task_id, 
            models.TaskStatus.COMPLETED, 
            output=f"AI Task Completed. Generated {len(generated_content)} chars."
        )

        crud.create_log(db, "FILE_CREATED", f"Created file: {file_name} (Task: {task.title})", agent_id=agent.id)
            
        # Update file list
        task.output_files = [file_name]
        task.output_text = generated_content[:500] + "..." # Store preview
        db.commit()
            
        # [PROJECT FEEDBACK LOOP]
        if task.project_file and os.path.exists(task.project_file):
            print(f"DEBUG: Updating Project File: {task.project_file}")
            
            # 1. Mark Step as Completed
            # We assume the step instruction is contained in task.input_prompt
            # But task.input_prompt might be long.
            # However, 'mark_step_completed' matches partial content.
            # Since we generated the task FROM the step text, it should match.
            project_manager.mark_step_completed(task.project_file, task.input_prompt[:50]) # Match first 50 chars
            
            # 2. Get Next Step
            next_step = project_manager.get_next_pending_step(task.project_file)
            
            if next_step:
                print(f"DEBUG: Found Next Project Step: {next_step}")
                
                # Parse "Agent: Instruction"
                if ":" in next_step:
                    target_name, instruction = next_step.split(":", 1)
                    target_name = target_name.strip()
                    instruction = instruction.strip()
                    
                    # Find Agent
                    target_agent = db.query(models.Agent).filter(models.Agent.name.contains(target_name)).first()
                    if target_agent:
                        # Create Next Task
                        new_task = schemas.TaskCreate(
                            title=f"Project Task: {target_name}",
                            input_prompt=instruction,
                            agent_id=target_agent.id,
                            project_file=task.project_file # Pass the baton
                        )
                        
                        next_task = crud.create_task(db, new_task)
                        
                        # Log to Company Log so Secretary knows
                        crud.create_log(db, "PROJECT_UPDATE", f"Step completed. Auto-starting next step for {target_name}: {instruction}", agent_id="System")
                        
                        # Recursive Call? No, separate thread/process to avoid stack depth
                        # In FastAPI BackgroundTasks, we can't easily add more.
                        # But we are in a thread. We can spawn another.
                        import threading
                        t = threading.Thread(target=process_task_background, args=(next_task.id,))
                        t.start()
                    else:
                        crud.create_log(db, "PROJECT_ERROR", f"Could not find agent '{target_name}' for next step.", agent_id="System")
            else:
                print("DEBUG: Project Execution Complete!")
                crud.create_log(db, "PROJECT_COMPLETE", f"All steps in {os.path.basename(task.project_file)} are done.", agent_id="System")
            
    except Exception as e:
        error_msg = f"AI Execution Failed: {str(e)}"
        print(error_msg)
        
        # Write detailed error log to file for user debugging
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ERROR_LOG = os.path.join(BASE_DIR, "outputs", "error_log.txt")
        os.makedirs(os.path.dirname(ERROR_LOG), exist_ok=True)
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.utcnow()}] Task {task_id}:\n{traceback.format_exc()}\n")
            
        crud.update_task_status(
            db, 
            task_id, 
            models.TaskStatus.FAILED, 
            output=error_msg + " (See outputs/error_log.txt)"
        )
    finally:
        db.close()


# --- Agent Endpoints ---
@app.post("/agents/", response_model=schemas.Agent)
def create_agent(agent: schemas.AgentCreate, db: Session = Depends(get_db)):
    return crud.create_agent(db=db, agent=agent)

@app.get("/agents/", response_model=List[schemas.Agent])
def read_agents(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    agents = crud.get_agents(db, skip=skip, limit=limit)
    return agents

@app.get("/agents/{agent_id}", response_model=schemas.Agent)
def read_agent(agent_id: str, db: Session = Depends(get_db)):
    db_agent = crud.get_agent(db, agent_id=agent_id)
    if db_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return db_agent



@app.put("/agents/{agent_id}", response_model=schemas.Agent)
def update_agent(agent_id: str, agent_update: schemas.AgentUpdate, db: Session = Depends(get_db)):
    db_agent = crud.update_agent(db, agent_id=agent_id, agent_update=agent_update)
    if db_agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return db_agent

@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    return crud.delete_agent(db=db, agent_id=agent_id)

# --- Chat Endpoints ---
@app.post("/chat/")
def chat_with_agent(chat_request: schemas.ChatRequest, db: Session = Depends(get_db)):
    # 1. Get Agent
    agent = crud.get_agent(db, agent_id=chat_request.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
        
    # 2. Get Config
    config = get_llm_config(db)
    if not config["api_key"]:
        raise HTTPException(status_code=500, detail="API Key not configured")
        
    # 3. Call LLM (Streaming)
    try:
        import json
        
        # Determine Task Mode
        # If force_execution is True, we use "dispatch" mode (for delegated tasks)
        # Otherwise "chat" mode (interactive)
        mode = "dispatch" if chat_request.force_execution else "chat"
        
        response = call_llm_service(
            agent, 
            chat_request.message, 
            config, 
            stream=True, 
            db=db, 
            history=chat_request.history,
            task_mode=mode
        )
        
        def event_generator():
            full_content = ""
            try:
                for line in response.iter_lines():
                    if line:
                        decoded = line.decode('utf-8')
                        if decoded.startswith("data: "):
                            content = decoded[6:]
                            if content == "[DONE]":
                                break
                            try:
                                data = json.loads(content)
                                delta = data['choices'][0]['delta'].get('content', "")
                                if delta:
                                    full_content += delta
                                    yield delta
                            except:
                                pass
            except Exception as e:
                yield f"[ERROR: {str(e)}]"
            
            # Post-processing: Check for [[LOG:...]] and [[EXECUTE_TASK:...]]
            try:
                import re
                
                # 1. Auto-Log
                match_log = re.search(r"\[\[LOG:(.*?)\]\]", full_content, re.DOTALL)
                if match_log:
                    log_text = match_log.group(1).strip()
                    crud.create_log(db, "MEETING_LOG", log_text, agent_id=agent.id)
                    
                # 2. Execute Task (Single)
                match_task = re.search(r"\[\[EXECUTE_TASK:(.*?)\|(.*?)\]\]", full_content, re.DOTALL)
                if match_task:
                    title = match_task.group(1).strip()
                    prompt = match_task.group(2).strip()
                    # (Legacy support, maybe unused now consistent with DELEGATE)
                    pass

                # 3. Create Project & Auto-Delegate First Step
                match_proj = re.search(r"\[\[CREATE_PROJECT:(.*?)\]\]", full_content, re.DOTALL)
                if match_proj:
                    content = match_proj.group(1).strip()
                    parts = [p.strip() for p in content.split("|")]
                    if len(parts) >= 2:
                        title = parts[0]
                        steps = parts[1:]
                        
                        # 1. Create File
                        proj_path = project_manager.create_project_file(title, steps)
                        yield f"\n\n🚀 **Project Created**: `{os.path.basename(proj_path)}`\n"
                        
                        # 2. Get Next Step
                        next_step = project_manager.get_next_pending_step(proj_path)
                        if next_step:
                            # Parse "Agent: Instruction"
                            if ":" in next_step:
                                target_name, instruction = next_step.split(":", 1)
                                target_name = target_name.strip()
                                instruction = instruction.strip()
                                
                                # Find Agent ID
                                all_agents = crud.get_agents(db) # We are inside a dependency scope? Yes, db is available.
                                target_agent = next(
                                    (a for a in all_agents if target_name in a.name or a.name in target_name), 
                                    None
                                )
                                
                                if target_agent:
                                    # Create Task linked to Project
                                    new_task = schemas.TaskCreate(
                                        title=f"Project Task: {target_name}",
                                        input_prompt=instruction,
                                        agent_id=target_agent.id,
                                        project_file=proj_path # LINKED!
                                    )
                                    db_task = crud.create_task(db, new_task)
                                    
                                    import threading
                                    t = threading.Thread(target=process_task_background, args=(db_task.id,))
                                    t.start()
                                    
                                    yield f"👉 **Auto-Started Step 1**: Delegated to `{target_name}`\n"
                                else:
                                    yield f"⚠️ **Error**: Could not find agent '{target_name}' for Step 1.\n"
                        else:
                            yield "✅ **Project Complete** (No steps?)\n"

            except Exception as e:
                print(f"Post-processing failed: {e}")
                yield f"\n[System Error: {str(e)}]"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
         raise HTTPException(status_code=500, detail=str(e))

# --- Task Endpoints ---
@app.post("/tasks/", response_model=schemas.Task)
def create_task(
    task: schemas.TaskCreate, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(get_db)
):
    agent = crud.get_agent(db, agent_id=task.agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    db_task = crud.create_task(db=db, task=task)
    # BackgroundTasks handling - remove db argument
    background_tasks.add_task(process_task_background, db_task.id)
    return db_task

@app.get("/tasks/", response_model=List[schemas.Task])
def read_tasks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_tasks(db, skip=skip, limit=limit)

# --- Settings Endpoints ---
@app.post("/settings/")
def update_setting(setting: schemas.SettingCreate, db: Session = Depends(get_db)):
    return crud.set_setting(db, setting.key, setting.value)

@app.get("/settings/{key}")
def read_setting(key: str, db: Session = Depends(get_db)):
    setting = crud.get_setting(db, key)
    if not setting:
        return {"key": key, "value": None}
    return setting

# --- Skill Endpoints ---
@app.get("/skills/", response_model=List[schemas.Skill])
def read_skills(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_skills(db, skip=skip, limit=limit)

# --- Log Endpoints ---
@app.post("/logs/decision", response_model=schemas.SystemLog)
def log_decision(log: schemas.LogCreate, db: Session = Depends(get_db)):
    return crud.create_log(db, "DECISION", log.content, agent_id=log.agent_id)
