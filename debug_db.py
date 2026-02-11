from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.models import Task, Agent, Setting, Base

SQLALCHEMY_DATABASE_URL = "sqlite:///company_ai.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

print("--- Settings ---")
settings = db.query(Setting).all()
for s in settings:
    print(f"{s.key}: {s.value}")

print("\n--- Agents ---")
agents = db.query(Agent).all()
for a in agents:
    print(f"ID: {a.id} | Name: {a.name} | Model: {a.model_name}")

print("\n--- Tasks (Last 5) ---")
tasks = db.query(Task).order_by(Task.created_at.desc()).limit(5).all()
for t in tasks:
    print(f"ID: {t.id}")
    print(f"Status: {t.status}")
    print(f"Output Text: {t.output_text}")
    print(f"Output Files: {t.output_files}")
    print("-" * 20)

db.close()
