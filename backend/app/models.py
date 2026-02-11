from sqlalchemy import Column, String, Text, Float, DateTime, ForeignKey, Table, Enum, Integer
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.sqlite import JSON
import uu
import uuid
import enum
from datetime import datetime
from .database import Base

# Association Table for Many-to-Many relationship between Agents and Skills
agent_skills = Table(
    'agent_skills',
    Base.metadata,
    Column('agent_id', String, ForeignKey('agents.id')),
    Column('skill_id', String, ForeignKey('skills.id'))
)

class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    role = Column(String)
    avatar = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    system_prompt = Column(Text)
    model_name = Column(String, default="gpt-4-turbo")
    temperature = Column(Float, default=0.7)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    skills = relationship("Skill", secondary=agent_skills, back_populates="agents")
    tasks = relationship("Task", back_populates="agent")

class Skill(Base):
    __tablename__ = "skills"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    # Relationships
    agents = relationship("Agent", secondary=agent_skills, back_populates="skills")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String)
    agent_id = Column(String, ForeignKey('agents.id'))
    status = Column(String, default=TaskStatus.PENDING.value)
    input_prompt = Column(Text)
    output_text = Column(Text, nullable=True)
    output_files = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)

    # Relationships
    agent = relationship("Agent", back_populates="tasks")

class Setting(Base):
    __tablename__ = "settings"
    
    # We only need one row, using key as PK
    key = Column(String, primary_key=True, index=True) 
    value = Column(String, nullable=True)
