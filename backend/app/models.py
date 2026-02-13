from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Table, Enum, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import JSON
import uu
import uuid
import enum
from datetime import datetime
from .database import Base

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

# Association Object for Many-to-Many relationship with extra columns
class AgentSkill(Base):
    __tablename__ = 'agent_skills'
    
    agent_id = Column(String, ForeignKey('agents.id'), primary_key=True)
    skill_id = Column(String, ForeignKey('skills.id'), primary_key=True)
    enabled = Column(Integer, default=1) # 1=Enabled, 0=Disabled
    config = Column(JSON, nullable=True) # Per-agent configuration overrides

    # Relationships
    agent = relationship("Agent", back_populates="agent_skills")
    skill = relationship("Skill", back_populates="skill_agents")

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    role = Column(String)
    job_title = Column(String, nullable=True) # 职称
    department = Column(String, nullable=True) # 部门
    level = Column(String, nullable=True) # 等级
    avatar = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text)
    model_name = Column(String, default="gpt-4-turbo")
    provider = Column(String, default="openai") # openai, gemini, etc.
    temperature = Column(Float, default=0.7)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    tasks = relationship("Task", back_populates="agent")
    logs = relationship("SystemLog", back_populates="agent")
    agent_skills = relationship("AgentSkill", back_populates="agent", cascade="all, delete-orphan")
    
    # Expose skills directly for Pydantic serialization
    skills = relationship("Skill", secondary="agent_skills", viewonly=True)
    
    agent_handbooks = relationship("AgentHandbook", back_populates="agent", cascade="all, delete-orphan")
    handbooks = relationship("Handbook", secondary="agent_handbooks", viewonly=True) 

class Skill(Base):
    __tablename__ = "skills"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True, unique=True) # e.g. "image_generation"
    display_name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    parameters_schema = Column(JSON, nullable=True) # JSON Schema for args

    # Relationships
    skill_agents = relationship("AgentSkill", back_populates="skill")

# --- Employee Handbooks ---
class AgentHandbook(Base):
    __tablename__ = 'agent_handbooks'
    
    agent_id = Column(String, ForeignKey('agents.id'), primary_key=True)
    handbook_id = Column(String, ForeignKey('handbooks.id'), primary_key=True)
    
    agent = relationship("Agent", back_populates="agent_handbooks")
    handbook = relationship("Handbook", back_populates="handbook_agents")

class Handbook(Base):
    __tablename__ = "handbooks"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True, unique=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    handbook_agents = relationship("AgentHandbook", back_populates="handbook")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String)
    agent_id = Column(String, ForeignKey('agents.id'))
    status = Column(String, default=TaskStatus.PENDING.value)
    input_prompt = Column(Text)
    output_text = Column(Text, nullable=True)
    output_files = Column(JSON, nullable=True)
    project_file = Column(String, nullable=True) # Link to Project Markdown File
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    # Relationships
    agent = relationship("Agent", back_populates="tasks")

class Setting(Base):
    __tablename__ = "settings"
    
    # We only need one row, using key as PK
    key = Column(String, primary_key=True, index=True) 
    value = Column(String, nullable=True)

class SystemLog(Base):
    __tablename__ = "system_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    event_type = Column(String) 
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent")
