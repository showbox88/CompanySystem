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

    agent_provider = config.get("agent_provider", "openai")
    
    # --- BRANCH: Google Gemini (Imagen) ---
    if agent_provider == "gemini":
        return _generate_image_gemini(config, prompt)

    # --- BRANCH: OpenAI (DALL-E 3) ---
    api_key = config.get("api_key")
    agent_name = config.get("agent_name", "Unknown_Agent") # Receive agent identity
    base_url = config.get("base_url", "https://api.openai.com/v1")
    
    if not api_key:
        return "[ERROR: OpenAI API Key is missing. Please configure it in Settings.]"

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
            
        print(f"DEBUG: Calling Image API (OpenAI): {image_url_endpoint} with prompt: {prompt}")

        response = requests.post(image_url_endpoint, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            url = data['data'][0]['url']
            return _download_and_return_markdown(url, agent_name, prompt)
        else:
            return f"[ERROR: Image Generation Failed. Status: {response.status_code}. Details: {response.text}]"

    except Exception as e:
        return f"[ERROR: Exception during image generation: {str(e)}]"

def _generate_image_gemini(config: Dict[str, Any], prompt: str) -> str:
    """
    Helper to generate image using Google Imagen (via Gemini API).
    """
    api_key = config.get("gemini_api_key")
    agent_name = config.get("agent_name", "Unknown_Agent")
    
    if not api_key:
        return "[ERROR: Gemini API Key is missing. Please configure it in Settings.]"
        
    # Endpoint for Imagen 3
    # Note: As of late 2024/2025, the endpoint is typically:
    # POST https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key=YOUR_API_KEY
    # Or newer versions. We'll use a likely stable one.
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={api_key}"
    
    headers = {
        "Content-Type": "application/json"
    }
    
    payload = {
        "instances": [
            {
                "prompt": prompt
            }
        ],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1" # "1:1", "3:4", "4:3", "16:9", "9:16"
        }
    }
    
    try:
        print(f"DEBUG: Calling Image API (Gemini): {url} with prompt: {prompt}")
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            data = response.json()
            # Imagen returns base64 encoded image
            # Structure: { "predictions": [ { "bytesBase64Encoded": "..." } ] }
            if "predictions" in data and len(data["predictions"]) > 0:
                b64_data = data["predictions"][0].get("bytesBase64Encoded")
                if b64_data:
                    return _save_base64_image(b64_data, agent_name, prompt)
            
            return f"[ERROR: No image data returned by Imagen. Response: {str(data)[:200]}...]"
        else:
            return f"[ERROR: Gemini Image Gen Failed. Status: {response.status_code}. Details: {response.text}]"
            
    except Exception as e:
        return f"[ERROR: Exception during Gemini image generation: {str(e)}]"

def _save_base64_image(b64_data: str, agent_name: str, prompt: str) -> str:
    import base64
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        agent_name_clean = "".join([c for c in agent_name if c.isalnum() or c in (' ', '-', '_', '(', ')')]).strip()
        ASSETS_DIR = os.path.join(BASE_DIR, "Company Doc", agent_name_clean, "assets")
        os.makedirs(ASSETS_DIR, exist_ok=True)
        
        timestamp = int(time.time())
        filename = f"img_{timestamp}.png"
        file_path = os.path.join(ASSETS_DIR, filename)
        
        with open(file_path, "wb") as f:
            f.write(base64.b64decode(b64_data))
            
        print(f"Image saved to: {file_path}")
        return f"![Generated Image](assets/{filename})\n\n*(Prompt: {prompt})*"
    except Exception as e:
        return f"[ERROR: Failed to save base64 image: {str(e)}]"

def _download_and_return_markdown(url: str, agent_name: str, prompt: str) -> str:
    # Reuse existing download logic
    try:
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        agent_name_clean = "".join([c for c in agent_name if c.isalnum() or c in (' ', '-', '_', '(', ')')]).strip()
        ASSETS_DIR = os.path.join(BASE_DIR, "Company Doc", agent_name_clean, "assets")
        os.makedirs(ASSETS_DIR, exist_ok=True)
        
        print(f"Downloading image from {url}...")
        img_response = requests.get(url, timeout=30)
        if img_response.status_code == 200:
            timestamp = int(time.time())
            filename = f"img_{timestamp}.png"
            file_path = os.path.join(ASSETS_DIR, filename)
            
            with open(file_path, "wb") as f:
                f.write(img_response.content)
                
            print(f"Image saved to: {file_path}")
            return f"![Generated Image](assets/{filename})\n\n*(Prompt: {prompt})*"
        else:
            return f"![Generated Image]({url})\n\n*(Warning: Failed to download image locally. Link expires soon.)*"
            
    except Exception as dl_error:
        print(f"Image Download Failed: {dl_error}")
        return f"![Generated Image]({url})\n\n*(Warning: Failed to save image locally.)*"

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
        # AUTO-DISCOVERY V2: Smart Fuzzy Match & Newest First
        # 1. Exact match (if file exists recursively)
        # 2. Prefix match (e.g. "Report.md" matches "Report_HASH.md")
        
        search_name = os.path.basename(clean_path)
        search_stem = os.path.splitext(search_name)[0] # "Report" from "Report.md"
        
        candidates = []
        for root, dirs, files in os.walk(COMPANY_DOC_DIR):
            for file in files:
                # Candidate 1: Exact Filename Match
                if file == search_name:
                    candidates.append(os.path.join(root, file))
                    continue
                
                # Candidate 2: Prefix Match with Hash (file starts with "Report" and ends with ".md")
                # Ensure we don't match "ReportALL.md" if looking for "Report"
                if file.startswith(search_stem) and file.endswith(".md"):
                     candidates.append(os.path.join(root, file))
        
        if candidates:
            # Sort by modification time (Newest First)
            candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            target_path = candidates[0]
            # Optional: We could return a note saying "Auto-selected latest file: ..."
        else:
             return f"[ERROR: File not found: {file_path}. (Searched for exact name and latest version starting with '{search_stem}')]"
             
    # Final Check
    if os.path.exists(target_path):
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
