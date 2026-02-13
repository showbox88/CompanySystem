
# Workflow Definitions
# Agents map their tasks to these Standard Operating Procedures (SOPs).

WORKFLOW_REGISTRY = {
    "general_task": {
        "name": "General Execution Protocol",
        "description": "Standard process for general tasks.",
        "steps": [
            "1. Analyze Request: Identify core objective and constraints.",
            "2. Information Gathering: Search logs or read files if context is missing.",
            "3. Execution: Perform the task.",
            "4. Output: Generate the final file content."
        ]
    },
    "visual_design": {
        "name": "Visual Asset Production Protocol",
        "description": "For tasks involving image generation, design, or artistic creation.",
        "steps": [
            "1. Asset Retrieval: Check logs for reference files (descriptions, prompts). Use 'read_file' if found.",
            "2. Prompt Engineering: Create a detailed image generation prompt based on references.",
            "3. Asset Generation: Call 'image_generation' skill.",
            "4. Validation: Briefly confirm the image URL was generated.",
            "5. Final Report: Create a Markdown file displaying the image and explaining the design."
        ]
    },
    "content_creation": {
        "name": "Content Drafting Protocol",
        "description": "For writing reports, articles, descriptions, or code.",
        "steps": [
            "1. Context Analysis: Determine tone, audience, and key points.",
            "2. Reference Check: Look for source materials in logs.",
            "3. Drafting: Write the content.",
            "4. Review: Ensure all user constraints are met.",
            "5. Final Output: Save as a Markdown file."
        ]
    }
}

def get_workflow(workflow_id: str):
    return WORKFLOW_REGISTRY.get(workflow_id, WORKFLOW_REGISTRY["general_task"])

def get_all_workflows_prompt():
    """Returns a string description of all workflows for the Secretary."""
    prompt = "AVAILABLE WORKFLOWS (Select one for the Delegate):\n"
    for w_id, w_data in WORKFLOW_REGISTRY.items():
        prompt += f"- ID: '{w_id}' | Name: {w_data['name']} | Purpose: {w_data['description']}\n"
    return prompt
