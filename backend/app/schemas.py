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
    job_title: Optional[str] = None
    department: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None
    system_prompt: str
    model_name: str = "gpt-4-turbo"
    temperature: float = 0.7
    avatar: Optional[str] = None

class SkillBase(BaseModel):
    name: str
    display_name: Optional[str] = None
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
    skills: Optional[List[str]] = [] # List of Skill IDs

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    level: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    avatar: Optional[str] = None
    skills: Optional[List[str]] = None # List of Skill IDs to Replace existing

class SkillCreate(SkillBase):
    pass

class TaskCreate(TaskBase):
    pass

class ChatMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class ChatRequest(BaseModel):
    agent_id: str
    message: str
    history: List[ChatMessage] = []
    force_execution: bool = False  # New field for delegated tasks

class ChatResponse(BaseModel):
    response: str

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

class LogCreate(BaseModel):
    agent_id: Optional[str] = None
    event_type: str
    content: str

class SystemLog(BaseModel):
    id: str
    agent_id: Optional[str]
    event_type: str
    content: str
    timestamp: datetime

    class Config:
        from_attributes = True
