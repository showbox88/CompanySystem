import os
import datetime

PROJECTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Company Doc", "Projects")

if not os.path.exists(PROJECTS_DIR):
    os.makedirs(PROJECTS_DIR)

def create_project_file(title: str, steps: list[str], is_sequential: bool = True) -> str:
    """Creates a new project markdow file. Returns the absolute path."""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"Project_{timestamp}_{title.replace(' ', '_')}.md"
    filepath = os.path.join(PROJECTS_DIR, filename)
    
    content = f"# Project: {title}\n"
    content += f"**Created**: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += f"**Status**: IN_PROGRESS\n\n"
    
    # Metadata for Execution Mode
    box = "[x]" if is_sequential else "[ ]"
    content += f"{box} Sequential Execution (Strict Order)\n\n"
    
    content += "## Execution Plan (Checklist)\n"
    
    for step in steps:
        # Steps typically come as "Agent | Instruction"
        content += f"- [ ] {step}\n"
        
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    return filepath

def mark_step_completed(filepath: str, step_content_part: str):
    """Marks a checklist item as [x] if it matches the partial content."""
    if not os.path.exists(filepath):
        return False
        
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    new_lines = []
    found = False
    for line in lines:
        if "- [ ]" in line and step_content_part in line:
            new_lines.append(line.replace("- [ ]", "- [x]", 1))
            found = True
        else:
            new_lines.append(line)
            
    if found:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
            
    return found

def get_pending_steps(filepath: str) -> list[str]:
    """
    Returns a list of pending steps to execute NEXT.
    - If [x] Sequential: Returns ONLY the first pending step.
    - If [ ] Sequential: Returns ALL pending steps.
    """
    if not os.path.exists(filepath):
        return []
        
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    # Check Mode
    is_sequential = True # Default
    for line in lines:
        if "Sequential Execution" in line:
            if "[ ]" in line:
                is_sequential = False
            break
            
    pending_steps = []
    for line in lines:
        if line.strip().startswith("- [ ]"):
            step = line.strip().replace("- [ ]", "").strip()
            pending_steps.append(step)
            
            if is_sequential:
                return [step] # Return immediately if sequential
                
    return pending_steps 

def get_next_pending_step(filepath: str):
    """Legacy wrapper for compatibility."""
    steps = get_pending_steps(filepath)
    return steps[0] if steps else None
