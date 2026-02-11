from sqlalchemy.orm import Session
from . import models, schemas
import uuid
from datetime import datetime

# --- Agent CRUD ---
def get_agent(db: Session, agent_id: str):
    return db.query(models.Agent).filter(models.Agent.id == agent_id).first()

def get_agents(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Agent).offset(skip).limit(limit).all()

def create_agent(db: Session, agent: schemas.AgentCreate):
    db_agent = models.Agent(
        id=str(uuid.uuid4()),
        name=agent.name,
        role=agent.role,
        description=agent.description,
        system_prompt=agent.system_prompt,
        model_name=agent.model_name,
        temperature=agent.temperature,
        avatar=agent.avatar
    )
    db.add(db_agent)
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
        status=models.TaskStatus.PENDING.value
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
