
import sys
import os
import pandas as pd

# Add parent to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import SessionLocal
from backend.app.models import Skill, AgentSkill, Agent

def inspect():
    db = SessionLocal()
    try:
        print("\n=== 1. SKILLS DEFINED IN DATABASE (Table: skills) ===")
        skills = db.query(Skill).all()
        data = [{"ID": s.id[:8], "Name": s.name, "Display": s.display_name} for s in skills]
        print(pd.DataFrame(data))

        print("\n=== 2. SKILL ASSIGNMENTS (Table: agent_skills) ===")
        assignments = db.query(AgentSkill).all()
        data2 = []
        for a in assignments:
            agent = db.query(Agent).filter(Agent.id == a.agent_id).first()
            skill = db.query(Skill).filter(Skill.id == a.skill_id).first()
            data2.append({
                "Agent": agent.name if agent else a.agent_id,
                "Skill": skill.name if skill else a.skill_id,
                "Enabled": a.enabled,
                "Config": a.config
            })
        if data2:
            print(pd.DataFrame(data2))
        else:
            print("No assignments found.")

    finally:
        db.close()

if __name__ == "__main__":
    inspect()
