from sqlalchemy.orm import Session
from . import models, schemas
import uuid
from datetime import datetime

# --- Agent CRUD ---
def get_agent(db: Session, agent_id: str):
    return db.query(models.Agent).filter(models.Agent.id == agent_id).first()

def get_agents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Agent).offset(skip).limit(limit).all()

def get_skills(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Skill).offset(skip).limit(limit).all()

def sync_skills(db: Session, registry_skills: dict):
    """
    Syncs in-memory registered skills to the database.
    """
    for name, data in registry_skills.items():
        db_skill = db.query(models.Skill).filter(models.Skill.name == name).first()
        if not db_skill:
            # Create new skill
            new_skill = models.Skill(
                id=str(uuid.uuid4()),
                name=name,
                display_name=data.get("display_name", name),
                description=data.get("description", "")
            )
            db.add(new_skill)
        else:
            # Update existing? (Optional, but good for description updates)
            db_skill.description = data.get("description", "")
            db_skill.display_name = data.get("display_name", name)
            
    db.commit()

def create_agent(db: Session, agent: schemas.AgentCreate):
    db_agent = models.Agent(
        id=str(uuid.uuid4()),
        name=agent.name,
        role=agent.role,
        job_title=agent.job_title,
        department=agent.department,
        level=agent.level,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model_name=agent.model_name,
        temperature=agent.temperature,
        avatar=agent.avatar
    )
    db.add(db_agent)
    db.commit()
    db.refresh(db_agent)
    
    # Handle Skills
    if agent.skills:
        for skill_id in agent.skills:
            # Check validity
            skill = db.query(models.Skill).filter(models.Skill.id == skill_id).first()
            if skill:
                 agent_skill = models.AgentSkill(agent_id=db_agent.id, skill_id=skill.id)
                 db.add(agent_skill)
        db.commit()
        db.refresh(db_agent)
        
    return db_agent

def update_agent(db: Session, agent_id: str, agent_update: schemas.AgentUpdate):
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not db_agent:
        return None
    
    # Filter out None values
    update_data = agent_update.model_dump(exclude_unset=True)
    
    # Handle Skills separately if present
    if "skills" in update_data:
        skill_ids = update_data.pop("skills") # Remove from setattr loop
        
        # 1. Clear existing skills
        db.query(models.AgentSkill).filter(models.AgentSkill.agent_id == agent_id).delete()
        
        # 2. Add new skills
        if skill_ids:
            for sid in skill_ids:
                skill = db.query(models.Skill).filter(models.Skill.id == sid).first()
                if skill:
                    new_as = models.AgentSkill(agent_id=agent_id, skill_id=sid)
                    db.add(new_as)
        
    for key, value in update_data.items():
        setattr(db_agent, key, value)
    
    db.commit()
    db.refresh(db_agent)
    return db_agent

def delete_agent(db: Session, agent_id: str):
    db_agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if db_agent:
        db.delete(db_agent)
        db.commit()
    return db_agent

# --- Task CRUD ---
def create_task(db: Session, task: schemas.TaskCreate):
    db_task = models.Task(
        id=str(uuid.uuid4()),
        title=task.title,
        agent_id=task.agent_id,
        input_prompt=task.input_prompt,
        status=models.TaskStatus.PENDING.value,
        project_file=task.project_file
    )
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

def get_tasks(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Task).offset(skip).limit(limit).all()

def update_task_status(db: Session, task_id: str, status: models.TaskStatus, output: str = None):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if db_task:
        db_task.status = status.value
        if output:
            db_task.output_text = output
            db_task.finished_at = datetime.utcnow()
        db.commit()
        db.refresh(db_task)
    return db_task

# --- Settings CRUD ---
def get_setting(db: Session, key: str):
    return db.query(models.Setting).filter(models.Setting.key == key).first()

def set_setting(db: Session, key: str, value: str):
    db_setting = db.query(models.Setting).filter(models.Setting.key == key).first()
    if db_setting:
        db_setting.value = value
    else:
        db_setting = models.Setting(key=key, value=value)
        db.add(db_setting)
    db.commit()
    db.refresh(db_setting)
    return db_setting

# --- System Logs ---
def create_log(db: Session, event_type: str, content: str, agent_id: str = None):
    # 1. Save to DB
    db_log = models.SystemLog(
        id=str(uuid.uuid4()),
        agent_id=agent_id,
        event_type=event_type,
        content=content
    )
    db.add(db_log)
    db.commit()
    db.refresh(db_log)

    # 2. Append to Markdown File
    try:
        import os
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        LOG_DIR = os.path.join(BASE_DIR, "Company Doc", "System")
        os.makedirs(LOG_DIR, exist_ok=True)
        LOG_FILE = os.path.join(LOG_DIR, "Company_Log.md")

        # Use Local Time (Server System Time)
        timestamp_str = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        agent_name = "System"
        if agent_id:
             agent = get_agent(db, agent_id)
             if agent:
                 agent_name = agent.name
        
        log_entry = f"\n- **[{timestamp_str}]** [{event_type}] ({agent_name}): {content}"
        
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_entry)
            
    except Exception as e:
        print(f"Failed to write to log file: {e}")

    return db_log

def get_recent_logs(db: Session, limit: int = 10):
    return db.query(models.SystemLog).order_by(models.SystemLog.timestamp.desc()).limit(limit).all()
