from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
import time
import os
from datetime import datetime
import traceback
import openai
from .database import engine, Base, get_db
from . import models, schemas, crud

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Company AI System")

# --- LLM Service ---
def get_llm_config(db: Session):
    api_key = crud.get_setting(db, "api_key")
    base_url = crud.get_setting(db, "base_url")
    return {
        "api_key": api_key.value if api_key else None,
        "base_url": base_url.value if base_url else "https://api.openai.com/v1"
    }

def process_task_background(task_id: str, db: Session):
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

    # 4. Call AI
    try:
        import requests
        
        # Construct URL
        # e.g. https://api.openai.com/v1 -> https://api.openai.com/v1/chat/completions
        base_url = config["base_url"].rstrip('/')
        if not base_url.endswith("/chat/completions"):
            api_url = f"{base_url}/chat/completions"
        else:
            api_url = base_url
            
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": agent.model_name,
            "messages": [
                {"role": "system", "content": agent.system_prompt},
                {"role": "user", "content": task.input_prompt}
            ],
            "temperature": agent.temperature
        }
        
        # Make direct HTTP request to avoid library conflicts
        response = requests.post(api_url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            raise Exception(f"API Error {response.status_code}: {response.text}")
            
        result = response.json()
        generated_content = result['choices'][0]['message']['content']
        
        # 5. Save to File
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        timestamp = int(time.time())
        # Sanitize title for filename
        clean_title = "".join([c for c in task.title if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        file_name = f"{clean_title}_{task_id[:8]}.md"
        file_path = os.path.join(OUTPUT_DIR, file_name)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(generated_content)
            
        # 6. Complete
        crud.update_task_status(
            db, 
            task_id, 
            models.TaskStatus.COMPLETED, 
            output=f"AI Task Completed. Generated {len(generated_content)} chars."
        )
        
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

@app.delete("/agents/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    return crud.delete_agent(db=db, agent_id=agent_id)

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
    background_tasks.add_task(process_task_background, db_task.id, db)
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
