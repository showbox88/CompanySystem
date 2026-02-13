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
    gemini_api_key = crud.get_setting(db, "gemini_api_key")
    return {
        "api_key": api_key.value if api_key else None,
        "base_url": base_url.value if base_url else "https://api.openai.com/v1",
        "gemini_api_key": gemini_api_key.value if gemini_api_key else None
    }

def call_gemini_service(agent: models.Agent, prompt: str, config: dict, stream: bool = False, history: List[schemas.ChatMessage] = [], system_prompt: str = ""):
    api_key = config.get("gemini_api_key")
    if not api_key:
        return "Error: Gemini API Key not configured."
    
    import requests
    import json

    model_name = agent.model_name or "gemini-1.5-pro"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    
    # Construct Gemini Content
    # Gemini uses "user" and "model" roles
    contents = []
    
    # 1. System Prompt (Hack: Prepend to first user message or use system_instruction if available in v1beta/1.5)
    # Ideally v1beta supports system_instruction, let's try strict formatting first.
    # For now, we prepend system prompt to the first user message context
    
    current_context = system_prompt + "\n\n"
    
    # 2. History
    # 2. History
    for msg in history:
        # Handle both Pydantic models (msg.role) and Dicts (msg['role'])
        if isinstance(msg, dict):
            role_val = msg.get("role")
            content_val = msg.get("content")
        else:
            role_val = msg.role
            content_val = msg.content
            
        role = "user" if role_val == "user" else "model"
        # Combine with current context if it's the very first message
        part_text = content_val
        if current_context:
            part_text = current_context + str(part_text)
            current_context = "" # Consumed
            
        contents.append({
            "role": role,
            "parts": [{"text": str(part_text)}]
        })
    
    # 3. Current Prompt
    final_prompt_text = prompt
    if current_context:
        final_prompt_text = current_context + final_prompt_text
        
    contents.append({
        "role": "user",
        "parts": [{"text": final_prompt_text}]
    })

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": agent.temperature,
            "maxOutputTokens": 8192
        }
    }
    
    if stream:
        # Stream implementation
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:streamGenerateContent?key={api_key}"
        try:
             # Use requests with stream=True
            with requests.post(url, json=payload, stream=True) as response:
                if response.status_code != 200:
                    yield f"Error: {response.status_code} - {response.text}"
                    return

                # Gemini streams a JSON array of partial objects, but slightly complex to parse raw.
                # However, the REST API returns "server-sent events" style or just a long JSON list?
                # Actually v1beta streamGenerateContent returns a stream of JSON objects.
                # Let's try simple line processing.
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        # Remove "data: " prefix if present (SSE) but Gemini usually sends raw JSON list items
                        if decoded_line.startswith(','): decoded_line = decoded_line[1:] # in case of array
                        if decoded_line.strip() == '[': continue
                        if decoded_line.strip() == ']': continue
                        
                        try:
                            # It might be a full JSON object per chunk
                            chunk_data = json.loads(decoded_line)
                            if "candidates" in chunk_data:
                                content_part = chunk_data["candidates"][0]["content"]["parts"][0]["text"]
                                yield content_part
                        except:
                            pass
        except Exception as e:
            yield f"Error calling Gemini: {str(e)}"

    else:
        # Non-stream implementation
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                data = response.json()
                if "candidates" in data:
                     return data["candidates"][0]["content"]["parts"][0]["text"]
                return "Error: No candidates returned."
            else:
                return f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error calling Gemini: {str(e)}"


def call_llm_service(agent: models.Agent, prompt: str, config: dict, stream: bool = False, db: Session = None, history: List[schemas.ChatMessage] = [], task_mode: str = "chat"):
    # Dispatch based on Provider
    if agent.provider == "gemini":
        # Pre-calculate system prompt to pass explicitly
        identity_prompt = (
            f"You are {agent.name}.\n"
            f"Role: {agent.role}\n"
            f"Job Title: {agent.job_title or 'N/A'}\n"
            f"Department: {agent.department or 'N/A'}\n"
            f"Level: {agent.level or 'N/A'}\n\n"
            f"{agent.system_prompt}"
        )
        # Inject logs
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        LOG_FILE = os.path.join(BASE_DIR, "Company Doc", "System", "Company_Log.md")
        if os.path.exists(LOG_FILE):
             try:
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    recent_lines = f.readlines()[-50:]
                    log_text = "".join(recent_lines)
                    identity_prompt += f"\n\n[Recent Company System Activity]\n{log_text}\n"
             except: pass
        
        # Inject Delegation or Dispatch instructions if needed
        # (This logic is duplicated from below but needed for proper system prompt construction)
        # For brevity, we pass the raw system prompt construction to the helper
        
        result = call_gemini_service(agent, prompt, config, stream, history, system_prompt=identity_prompt)
        
        # FIX: If not streaming, consume the generator immediately and return string
        if not stream:
            return "".join([chunk for chunk in result])
            
        return result
        
    # Default to OpenAI
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
    
    # Construct Identity Context (OpenAI)
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
            f"\n\n[INSTRUCTION: COMMAND ANALYSIS PROTOCOL]\n"
            "你是公司的调度员/秘书。为了确保准确性，你必须对接下来的每一条用户指令执行以下 2 步流程：\n"
            "\n"
            "### 第一步：分析 (思维沙盒)\n"
            "在决定如何行动之前，先输出一个 Markdown 表格进行分析：\n"
            "| 字段 | 值 |\n"
            "|---|---|\n"
            "| **用户意图** | (查询 / 指令 / 闲聊 / 项目计划) |\n"
            "| **关键实体** | (提到了谁？) |\n"
            "| **指令类型** | (例如：写文件, 回答问题, 分派任务, 制定计划) |\n"
            "| **工作流ID** | (从可用工作流中选择最匹配的，默认 'general_task') |\n"
            "| **目标是否存在?** | (检查公司目录是否匹配: 是/否) |\n"
            "\n"
            "### 第二步：行动\n"
            "根据上表分析结果：\n"
            "1. **如果意图 = 查询/闲聊** -> 直接回答。\n"
            "2. **如果意图 = 项目计划 (复杂/多步骤目标)**:\n"
            "   - 触发条件：用户使用了“先...后...”、“然后”、“基于...”、“First... Then...”等词。\n"
            "   - 触发条件：任务之间存在依赖关系（任务B需要任务A的产出）。\n"
            "   - 将目标分解为顺序执行的检查清单。\n"
            "   - **强制规则**：如果用户要求“写提示词/文案” **和** “生成图片”：\n"
            "     - 步骤 1: 写提示词/文案 (内容型员工)。\n"
            "     - 步骤 2: 根据步骤1生成图片 (视觉型员工)。\n"
            "     - **绝对禁止**在写好提示词之前就去画图。\n"
            "   - **判定模式**：串行 (默认) 还是 并行?\n"
            "     - 如果用户说“同时”、“一起”、“并发” -> 串行: False\n"
            "     - 否则 -> 串行: True\n"
            "   - **输出格式**: [[CREATE_PROJECT: {项目标题} | {是否串行(True/False)} | {步骤1} | {步骤2} ...]]\n"
            "   - **步骤格式**: '员工姓名: 具体指令' (例如 '小张: 写最后一段脚本')\n"
            "   - **示例**: [[CREATE_PROJECT: 科幻漫画项目 | True | 小张: 编写脚本 | 小美: 根据脚本绘制分镜]]\n"
            "\n"
            "3. **如果意图 = 指令 (单任务/并行任务)**:\n"
            "   - 触发条件：独立的任务，可以立即执行。\n"
            "   - 识别所有目标员工。\n"
            "   - **严重警告**：目标姓名必须与 [Company Directory Data] 中的 'Name' 列 **完全一致**。\n"
            "   - **绝对禁止**翻译名字 (例如：如果目录里是 '小张'，绝不要输出 'Xiao Zhang')。\n"
            "   - **绝对禁止**翻译指令内容，保持原意。\n"
            "   - 输出分派标签，每行一个。\n"
            "   - **标签格式**: [[DELEGATE: {准确的员工姓名} | {工作流ID} | {原始指令}]]\n"
            "   - **示例**: \n"
            "     [[DELEGATE: 小张 | content_creation | 写一份日报]]\n"
            "     [[DELEGATE: 小美 | visual_design | 画一辆科幻自行车]]\n"
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
                
                # DEBUG LOGGING (Commented out to reduce noise in System Log)
                print(f"DEBUG: Skill Execution Result: {skill_res_str}")
                # try:
                #     crud.create_log(db, "SKILL_DEBUG", f"Agent {agent.name} executed {tag_string}. Result: {skill_res_str[:200]}...", agent_id=agent.id)
                # except:
                #     pass

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
            
            # 2. Get Next Step(s)
            next_steps = project_manager.get_pending_steps(task.project_file) # Returns list (1 or many)
            
            if next_steps:
                print(f"DEBUG: Found {len(next_steps)} Next Project Steps.")
                
                # Iterate and spawn parallel if needed
                import threading

                for step_str in next_steps:
                    # Parse "Agent: Instruction"
                    if ":" in step_str:
                        target_name, instruction = step_str.split(":", 1)
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
                                project_file=task.project_file 
                            )
                            
                            next_task_obj = crud.create_task(db, new_task)
                            
                            # Log to Company Log
                            crud.create_log(db, "PROJECT_UPDATE", f"Step completed. Auto-starting next step for {target_name}: {instruction}", agent_id="System")
                            
                            # Spawn Thread
                            t = threading.Thread(target=process_task_background, args=(next_task_obj.id,))
                            t.start()
                            print(f"DEBUG: Spawned thread for task {next_task_obj.id}")
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

# --- Handbook Endpoints ---
@app.post("/handbooks/", response_model=schemas.Handbook)
def create_handbook(handbook: schemas.HandbookCreate, db: Session = Depends(get_db)):
    return crud.create_handbook(db=db, handbook=handbook)

@app.get("/handbooks/", response_model=List[schemas.Handbook])
def read_handbooks(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_handbooks(db, skip=skip, limit=limit)

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
                        
                        # Check 2nd arg for boolean
                        raw_seq = parts[1].lower()
                        if raw_seq in ["true", "yes", "sequential"]:
                            is_seq = True
                            steps = parts[2:]
                        elif raw_seq in ["false", "no", "parallel"]:
                            is_seq = False
                            steps = parts[2:]
                        else:
                            # Backward compatibility or implicit True
                            is_seq = True 
                            # If parts[1] looks like a step (contains ":"), assume True and start steps from index 1
                            if ":" in parts[1]:
                                steps = parts[1:]
                            else:
                                steps = parts[2:] # Maybe just a title and weird arg

                        # 1. Create File
                        proj_path = project_manager.create_project_file(title, steps, is_sequential=is_seq)  
                        mode_str = "Strict Sequential" if is_seq else "Parallel Execution"
                        yield f"\n\n🚀 **Project Created**: `{os.path.basename(proj_path)}` ({mode_str})\n"
                        
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
