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
                # Get last 15 lines
                recent_lines = lines[-15:]
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
            "\n\n[INSTRUCTION: COMMAND ANALYSIS PROTOCOL]\n"
            "You are a Scheduler/Dispatcher. To ensure accuracy, you MUST follow this 2-step process for EVERY user message:\n"
            "\n"
            "### STEP 1: ANALYZE (Mental Sandbox)\n"
            "Before deciding to delegate or answer, output a Markdown table analyzing the request:\n"
            "| Field | Value |\n"
            "|---|---|\n"
            "| **User Intent** | (QUERY / COMMAND / CHAT) |\n"
            "| **Key Entities** | (Who is mentioned?) |\n"
            "| **Command Type** | (e.g. Write File, Answer Question, Assign Task) |\n"
            "| **Valid Target?** | (Check Directory Pattern Matching: Yes/No) |\n"
            "\n"
            "### STEP 2: ACT\n"
            "Based on the table above:\n"
            "1. **IF INTENT = QUERY/CHAT**:\n"
            "   - Answer the question directly.\n"
            "   - DO NOT generate delegation tags.\n"
            "2. **IF INTENT = COMMAND**:\n"
            "   - Identify ALL targets.\n"
            "   - **CRITICAL**: The Target Name MUST match the 'Name' column in the [Company Directory Data] EXACTLY.\n"
            "   - DO NOT translate names (e.g. if directory says '小张', DO NOT output 'Xiao Zhang').\n"
            "   - **CRITICAL**: DO NOT TRANSLATE THE INSTRUCTION.\n"
            "   - OUTPUT THE DELEGATION TAGS, ONE PER LINE.\n"
            "   - TAG FORMAT: [[DELEGATE: {Exact Target Name from Directory} | {Original Instruction}]]\n"
            "   - EXAMPLE: \n"
            "     [[DELEGATE: 小张 | 写一份日报]]\n"
            "     [[DELEGATE: 小美 | Review the code]]\n"
        )

    # Inject Thinking Protocol (Cognitive Architecture)
    from .thoughts.engine import ThinkingEngine
    identity_prompt += ThinkingEngine.enrich_system_prompt(agent, db, context={"task_mode": task_mode})

    # 3. Task Mode Instructions

    # 3. Task Mode Instructions
    
    
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
                
            role = "assistant" if role_val == "assistant" else "user"
            messages.append({"role": role, "content": content_val})

        # Add current message
        messages.append({"role": "user", "content": prompt})

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
        system_msg = {"role": "system", "content": agent.system_prompt} # We'll re-fetch the full enriched prompt below
        
        # Re-construct the full identity prompt (similar to call_llm_service logic)
        # To avoid duplicating code, we might need to refactor call_llm_service to simply take messages? 
        # For now, let's rely on call_llm_service's ability to handle the "first" call, and then we manually handle subsequent calls?
        # Actually, call_llm_service currently constructs the system prompt internally every time.
        # This makes multi-turn hard if we don't pass `history` to it.
        # `call_llm_service` supports `history` param!
        
        task_history = [] 
        
        for turn in range(match_limit):
            print(f"DEBUG: Background Task Turn {turn+1}")
            
            # Call LLM
            # On first turn, history is empty.
            # On subsequent turns, history contains: [Assistant(Call), User(Result)]
            
            response_text = call_llm_service(
                agent, 
                task.input_prompt if turn == 0 else "Continue...", # Subsequent user prompts are dummy or "Result: ..."
                config, 
                db=db, 
                task_mode="file_generation",
                history=task_history
            )
            
            # If this is a subsequent turn, we must append the result to the LAST response? 
            # Wait, call_llm_service returns the NEW content.
            
            # Check for Skills
            from .skill_dispatcher import SkillDispatcher
            dispatcher = SkillDispatcher(db, agent)
            
            result_text = response_text
            executed_any = False
            
            # Parse ALL tags in this response
            import re
            # Regex to find [[CALL_SKILL: ...]]
            # We iterate until no more tags found in THIS response
            while True:
                match = re.search(r"\[\[CALL_SKILL:\s*(.*?)\]\]", result_text, re.DOTALL)
                if not match:
                    break
                
                tag_string = match.group(0)
                print(f"DEBUG: Found tag: {tag_string}")
                
                skill_result, executed = dispatcher.parse_and_execute(tag_string, config)
                
                # Replace the tag with the result in the text (so the file/history looks clean-ish)
                # Or do we keep the tag and append result?
                # Standard ReAct: Keep Thought, Append Observation.
                # Our "File Mode": We want the FINAL file to be clean. 
                # But for the Agent to "see" it, it needs to be in history.
                
                # Strategy: 
                # Replace tag with result in `result_text` (so it becomes part of the assistant's output/observation)
                # But wait, if we replace it, the agent sees the result *as if it wrote it*.
                # Better: 
                # 1. Add Assistant Message (with Tag) to history.
                # 2. Add User Message (System Observation) to history.
                # 3. Loop.
                
                # However, call_llm_service is designed to return a string, not manage history object statefully across calls easily 
                # unless we carefully construct `history`.
                
                # Let's try the "Replacement" strategy for the *File Content*, but needed for *Context*?
                # If we replace [[CALL]] with [RESULT], the Agent sees [RESULT] in its own past output? No.
                
                # Simpler implementation for this specific issue:
                # 1. If skill executed, we treat `skill_result` as a NEW piece of info.
                # 2. We append it to `task_history` as a System/User message.
                # 3. We let the Agent generate again.
                
                executed_any = True
                
                # Add the original assistant output (with tag) to history
                task_history.append({"role": "assistant", "content": tag_string}) # Just the tag? or whole text?
                # Using whole text might be too long if repeated. Let's use the tag interaction.
                
                # Add observation
                task_history.append({"role": "user", "content": f"System Output: {skill_result}"})
                
                # Remove the tag from the current result_text to avoid re-processing? 
                # No, we're building a chain.
                # Stop parsing this text, move to next turn.
                break 
            
            if executed_any:
                continue # loop to next turn (LLM will see result in history and generate next step)
            else:
                # No skills called. This is the Final Content.
                final_content = response_text
                break
        
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
                    
                # 2. Execute Task
                match_task = re.search(r"\[\[EXECUTE_TASK:(.*?)\|(.*?)\]\]", full_content, re.DOTALL)
                if match_task:
                    title = match_task.group(1).strip()
                    prompt = match_task.group(2).strip()
                    
                    # Create Task
                    new_task = schemas.TaskCreate(
                        title=title,
                        input_prompt=prompt,
                        agent_id=agent.id
                    )
                    db_task = crud.create_task(db, new_task)
                    
                    # Run in background
                    db_task = crud.create_task(db, new_task)
                    
                    # Run in background
                    import threading
                    # Launch the background processing directly
                    t = threading.Thread(target=process_task_background, args=(db_task.id,))
                    t.start()
                    
            except Exception as e:
                print(f"Post-processing failed: {e}")

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
