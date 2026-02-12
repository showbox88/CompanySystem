
import sys
import os

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import SessionLocal
from backend.app.models import Agent, Skill, AgentSkill

def setup_skills():
    db = SessionLocal()
    try:
        # 1. Find Xiao Mei (Designer)
        agent = db.query(Agent).filter(Agent.name.like("%小美%")).first()
        if not agent:
            print("Xiao Mei not found!")
            return

        print(f"Found Agent: {agent.name} ({agent.role})")

        # 2. Find Image Generation Skill
        skill = db.query(Skill).filter(Skill.name == "image_generation").first()
        if not skill:
            print("Skill 'image_generation' not found!")
            return
            
        print(f"Found Skill: {skill.display_name}")

        # 3. Assign Skill
        # Check if already assigned
        assignment = db.query(AgentSkill).filter(
            AgentSkill.agent_id == agent.id,
            AgentSkill.skill_id == skill.id
        ).first()

        if not assignment:
            print("Assigning skill...")
            new_assignment = AgentSkill(
                agent_id=agent.id,
                skill_id=skill.id,
                enabled=1,
                config={} 
            )
            db.add(new_assignment)
            db.commit()
            print("Skill Assigned Successfully!")
        else:
            print("Skill already assigned.")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    setup_skills()
