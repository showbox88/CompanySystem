from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
from enum import Enum

# --- Enums ---
class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# --- Shared Base Models ---
class AgentBase(BaseModel):
    name: str
    role: str
    description: Optional[str] = None
    system_prompt: str
    model_name: str = "gpt-4-turbo"
    temperature: float = 0.7
    avatar: Optional[str] = None

class SkillBase(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None

class TaskBase(BaseModel):
    title: str
    input_prompt: str
    agent_id: str

class SettingBase(BaseModel):
    key: str
    value: str

# --- Creation Models (Input) ---
class AgentCreate(AgentBase):
    pass

class SkillCreate(SkillBase):
    pass

class TaskCreate(TaskBase):
    pass

class SettingCreate(SettingBase):
    pass

# --- Reading Models (Output) ---
class Skill(SkillBase):
    id: str
    
    class Config:
        from_attributes = True

class Agent(AgentBase):
    id: str
    created_at: datetime
    skills: List[Skill] = []

    class Config:
        from_attributes = True

class Task(TaskBase):
    id: str
    status: TaskStatus
    output_text: Optional[str] = None
    output_files: Optional[List[str]] = None
    created_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class Setting(SettingBase):
    class Config:
        from_attributes = True
