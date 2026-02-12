
import sys
import os

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import engine, Base
from backend.app.models import AgentSkill, Skill, Agent
from backend.app import models
from sqlalchemy import text

def migrate():
    print("Starting Schema Migration...")
    
    with engine.connect() as conn:
        # 1. Drop old tables if they exist
        # We need to drop 'agent_skills' first due to FK
        try:
            print("Dropping 'agent_skills' table...")
            conn.execute(text("DROP TABLE IF EXISTS agent_skills"))
            conn.execute(text("DROP TABLE IF EXISTS skills"))
            conn.commit()
        except Exception as e:
            print(f"Error dropping tables: {e}")

    # 2. CRUD Create All
    # This will create any missing tables.
    # Since we dropped 'agent_skills' and 'skills', they will be recreated with new schema.
    print("Creating new tables...")
    Base.metadata.create_all(bind=engine)
    
    # 3. Seed Skills
    from backend.app.skills import SkillRegistry
    from sqlalchemy.orm import Session
    
    db = Session(bind=engine)
    try:
        registry = SkillRegistry.get_all_skills()
        for key, sk_data in registry.items():
            existing = db.query(Skill).filter(Skill.name == key).first()
            if not existing:
                print(f"Seeding Skill: {sk_data['display_name']}")
                new_skill = Skill(
                    name=key,
                    display_name=sk_data['display_name'],
                    description=sk_data['description'],
                    parameters_schema=sk_data['parameters']
                )
                db.add(new_skill)
        db.commit()
        print("Skill Seeding Complete.")
    except Exception as e:
        print(f"Error seeding skills: {e}")
    finally:
        db.close()

    print("Migration Finished Successfully.")

if __name__ == "__main__":
    migrate()
