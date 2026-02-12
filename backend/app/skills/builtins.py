import json
import os
import requests
import time
from typing import Dict, Any
from .registry import SkillRegistry

# --- Skill Implementations ---

@SkillRegistry.register(
    name="image_generation",
    display_name="AI Drawing (DALL-E 3)",
    description="Generate high-quality images based on text prompts.",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "The detailed description of the image to generate."},
            "size": {"type": "string", "enum": ["1024x1024"], "default": "1024x1024"}
        },
        "required": ["prompt"]
    }
)
def generate_image(config: Dict[str, Any], args: Dict[str, Any]) -> str:
    """
    Handler for Image Generation.
    Returns: Markdown String (image url) or Status Message.
    """
    prompt = args.get("prompt") or args.get("description")
    if not prompt:
        return "[ERROR: Missing 'prompt' argument. Please provide a description of what to draw.]"

    api_key = config.get("api_key")
    agent_name = config.get("agent_name", "Unknown_Agent") # Receive agent identity
    base_url = config.get("base_url", "https://api.openai.com/v1")
    
    if not api_key:
        return "[ERROR: API Key is missing. Please configure it in Settings.]"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024"
    }

    try:
        # Standard OpenAI Image Endpoint
        image_url_endpoint = f"{base_url}/images/generations"
        if "chat/completions" in base_url:
            image_url_endpoint = base_url.replace("chat/completions", "images/generations")
            
        print(f"DEBUG: Calling Image API: {image_url_endpoint} with prompt: {prompt}")

        response = requests.post(image_url_endpoint, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            url = data['data'][0]['url']
            
            # --- START DOWNLOAD LOGIC ---
            try:
                # 1. Determine Output Path
                # Go up 4 levels: skills -> app -> backend -> CompanySystem -> Root
                # path: .../backend/app/skills/builtins.py
                BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                
                # Sanitize agent name (Folder Name)
                agent_name_clean = "".join([c for c in agent_name if c.isalnum() or c in (' ', '-', '_', '(', ')')]).strip()
                ASSETS_DIR = os.path.join(BASE_DIR, "Company Doc", agent_name_clean, "assets")
                os.makedirs(ASSETS_DIR, exist_ok=True)
                
                # 2. Download Image
                print(f"Downloading image from {url}...")
                img_response = requests.get(url, timeout=30)
                if img_response.status_code == 200:
                    timestamp = int(time.time())
                    filename = f"img_{timestamp}.png"
                    file_path = os.path.join(ASSETS_DIR, filename)
                    
                    with open(file_path, "wb") as f:
                        f.write(img_response.content)
                        
                    print(f"Image saved to: {file_path}")
                    # 3. Return Local Path (Relative to md file in parent folder)
                    return f"![Generated Image](assets/{filename})\n\n*(Prompt: {prompt})*"
                else:
                    return f"![Generated Image]({url})\n\n*(Warning: Failed to download image locally. Link expires soon.)*"
                    
            except Exception as dl_error:
                print(f"Image Download Failed: {dl_error}")
                # Fallback to URL
                return f"![Generated Image]({url})\n\n*(Warning: Failed to save image locally.)*"
            
        else:
            return f"[ERROR: Image Generation Failed. Status: {response.status_code}. Details: {response.text}]"

    except Exception as e:
        return f"[ERROR: Exception during image generation: {str(e)}]"

@SkillRegistry.register(
    name="web_search",
    display_name="Web Search",
    description="Search the internet for real-time information.",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search usage keywords."}
        },
        "required": ["query"]
    }
)
def web_search(config: Dict[str, Any], args: Dict[str, Any]) -> str:
    # Placeholder for now
    return "[System: Web Search is not yet connected to a provider.]"

@SkillRegistry.register(
    name="read_file",
    display_name="Read Company Document",
    description="Read the content of a file from the Company Doc storage.",
    parameters={
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "The path to the file (relative to Company Doc or absolute)."}
        },
        "required": ["file_path"]
    }
)
def read_file(config: Dict[str, Any], args: Dict[str, Any]) -> str:
    """
    Safely reads a file from the Company Doc directory.
    """
    # Robust Argument Handling: Support file_path, path, filename, file
    file_path = args.get("file_path") or args.get("path") or args.get("filename") or args.get("file")
    
    if not file_path:
        return "[ERROR: Missing 'file_path' argument. Please specify the file to read.]"
        
    # Security: Resolve path and ensure it's within Company Doc
    # BASE_DIR = ...backend/app/skills/builtins.py -> up 4 levels to root
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    COMPANY_DOC_DIR = os.path.join(BASE_DIR, "Company Doc")
    
    # Normalize inputs
    # Handle "Company Doc/..." prefix repetition
    clean_path = file_path.replace("\\", "/")
    if clean_path.startswith("Company Doc/"):
        target_path = os.path.join(BASE_DIR, clean_path)
    # Handle absolute path provided by system output?
    elif os.path.isabs(clean_path):
        target_path = clean_path
    else:
        target_path = os.path.join(COMPANY_DOC_DIR, clean_path)
        
    target_path = os.path.abspath(target_path)
    
    # Boundary Check
    if not target_path.startswith(os.path.abspath(COMPANY_DOC_DIR)):
        return "[ERROR: Access Denied. You can only read files within 'Company Doc'.]"
        
    if not os.path.exists(target_path):
        # AUTO-DISCOVERY: If file not found, search for it recursively in Company Doc
        # This handles cases where Agent only knows filename but not the subdirectory (e.g. "Xiao Zhang/file.md")
        filename = os.path.basename(clean_path)
        found_path = None
        
        for root, dirs, files in os.walk(COMPANY_DOC_DIR):
            if filename in files:
                found_path = os.path.join(root, filename)
                break
        
        if found_path:
            target_path = found_path
        else:
            return f"[ERROR: File not found: {file_path} (Searched entire Company Doc directory)]"
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Limit content size?
            if len(content) > 10000:
                 return f"[FILE CONTENT (Truncated first 10k chars)]:\n{content[:10000]}...\n(File too large)"
            return f"[FILE CONTENT]:\n{content}"
    except Exception as e:
        return f"[ERROR: Failed to read file: {str(e)}]"

@SkillRegistry.register(
    name="list_files",
    display_name="List Company Documents",
    description="List all files in the Company Doc directory to find a specific document.",
    parameters={
        "type": "object",
        "properties": {
            "subdir": {"type": "string", "description": "Optional subdirectory to filter (e.g. 'Xiao Zhang')."}
        },
        "required": []
    }
)
def list_files(config: Dict[str, Any], args: Dict[str, Any]) -> str:
    """
    Lists files in Company Doc.
    """
    subdir = args.get("subdir", "")
    
    # Base Dir logic (same as read_file)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    COMPANY_DOC_DIR = os.path.join(BASE_DIR, "Company Doc")
    
    if subdir:
        # Sanitize subdir
        subdir = subdir.replace("\\", "/").strip("/")
        target_dir = os.path.join(COMPANY_DOC_DIR, subdir)
    else:
        target_dir = COMPANY_DOC_DIR
        
    if not os.path.exists(target_dir):
        return f"[ERROR: Directory not found: {subdir}]"
        
    # Walk and list
    file_list = []
    try:
        # If listing root, show subfolders (Agents)
        if not subdir:
            items = os.listdir(target_dir)
            files = [f for f in items if os.path.isfile(os.path.join(target_dir, f))]
            dirs = [d for d in items if os.path.isdir(os.path.join(target_dir, d))]
            return f"[CONTENTS of Company Doc]:\nDIRS: {', '.join(dirs)}\nFILES: {', '.join(files)}\n(Tip: Use subdir='AgentName' to see their files)"
        
        # If listing subdir, show files
        items = os.listdir(target_dir)
        files = [f for f in items if os.path.isfile(os.path.join(target_dir, f)) and not f.startswith(".")]
        return f"[FILES in {subdir}]:\n" + "\n".join(files)
    except Exception as e:
        return f"[ERROR: Failed to list files: {str(e)}]"
