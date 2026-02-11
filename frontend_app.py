import streamlit as st
import requests
import time
import pandas as pd
import os

# Configuration
API_URL = "http://localhost:8000"

st.set_page_config(page_title="AI Agent Company System", layout="wide")

st.title("🏭 AI Agent Company Management System")

# Sidebar Navigation
page = st.sidebar.radio("Navigation", ["Agent Center", "Task Console", "File Vault", "Settings"])

# --- Helper Functions (Optimized) ---
# Create a persistent session to speed up connections
if 'api_session' not in st.session_state:
    st.session_state['api_session'] = requests.Session()

def make_request(method, endpoint, **kwargs):
    """Unified request handler with session"""
    url = f"{API_URL}{endpoint}"
    try:
        if method == "GET":
            response = st.session_state['api_session'].get(url, **kwargs)
        elif method == "POST":
            response = st.session_state['api_session'].post(url, **kwargs)
        elif method == "DELETE":
            response = st.session_state['api_session'].delete(url, **kwargs)
        return response
    except requests.exceptions.ConnectionError:
        return None

# Use caching to avoid fetching data on every UI interaction (e.g. typing)
# TTL (Time To Live) set to 2 seconds for near real-time feel but preventing burst requests
@st.cache_data(ttl=2)
def get_agents():
    # We use a wrapper to allow caching, as the session object can't be hashed easily by st.cache
    # But here we just call the endpoint freshly if cache expired
    try:
        response = requests.get(f"{API_URL}/agents/")
        if response.status_code == 200:
            return response.json()
    except:
        return []
    return []

@st.cache_data(ttl=2)
def get_tasks():
    try:
        response = requests.get(f"{API_URL}/tasks/")
        if response.status_code == 200:
            return response.json()
    except:
        return []
    return []

# Clear cache when we make changes (Create/Delete)
def clear_cache():
    get_agents.clear()
    get_tasks.clear()

def create_agent(name, role, system_prompt):
    payload = {
        "name": name,
        "role": role,
        "system_prompt": system_prompt,
        "model_name": "gpt-4-turbo",
        "temperature": 0.7
    }
    res = make_request("POST", "/agents/", json=payload)
    if res and res.status_code == 200:
        clear_cache() # Force refresh
    return res

def create_task(agent_id, title, prompt):
    payload = {
        "title": title,
        "input_prompt": prompt,
        "agent_id": agent_id
    }
    res = make_request("POST", "/tasks/", json=payload)
    if res and res.status_code == 200:
        clear_cache()
    return res

def get_setting(key):
    # Settings rarely change, can cache longer (e.g. 10s)
    res = make_request("GET", f"/settings/{key}")
    if res and res.status_code == 200:
        return res.json().get("value", "")
    return ""

def save_setting(key, value):
    res = make_request("POST", "/settings/", json={"key": key, "value": value})
    return res is not None

# --- Page: Agent Center ---
if page == "Agent Center":
    st.header("👥 Agent Personnel Center")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Register New Agent")
        with st.form("new_agent_form"):
            new_name = st.text_input("Name", placeholder="e.g. Copywriter-01")
            new_role = st.text_input("Role", placeholder="e.g. Senior Copywriter")
            new_prompt = st.text_area("System Prompt", placeholder="You are an expert in...", height=150)
            submitted = st.form_submit_button("Create Agent")
            
            if submitted:
                if new_name and new_role and new_prompt:
                    res = create_agent(new_name, new_role, new_prompt)
                    if res and res.status_code == 200:
                        st.success("Agent Created Successfully!")
                        st.rerun()  # Refresh the page
                    elif res is None:
                        st.error("❌ Cannot connect to Backend API. Is it running?")
                    else:
                        st.error("Failed to create agent.")
                else:
                    st.warning("Please fill in all fields.")

    with col2:
        st.subheader("Active Agents")
        agents = get_agents()
        if agents:
            for agent in agents:
                with st.expander(f"**{agent['name']}** - {agent['role']}"):
                    st.write(f"**ID:** `{agent['id']}`")
                    st.markdown(f"**System Prompt:**\n> {agent['system_prompt']}")
                    if st.button("Delete Agent", key=f"del_{agent['id']}"):
                        make_request("DELETE", f"/agents/{agent['id']}")
                        clear_cache()
                        st.rerun()
        else:
            st.info("No agents found. Create one to get started.")

# --- Page: Task Console ---
elif page == "Task Console":
    st.header("⚡ Task Console")
    
    agents = get_agents()
    agent_options = {a['name']: a['id'] for a in agents}
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Assign Task")
        with st.form("new_task_form"):
            task_title = st.text_input("Task Title", placeholder="Generate Weekly Report")
            selected_agent_name = st.selectbox("Assign To", list(agent_options.keys()) if agent_options else ["No Agents Available"])
            task_prompt = st.text_area("Task Instructions", height=200)
            submitted = st.form_submit_button("🚀 Launch Task")
            
            if submitted and agent_options:
                agent_id = agent_options[selected_agent_name]
                res = create_task(agent_id, task_title, task_prompt)
                if res and res.status_code == 200:
                    st.success("Task dispatched to Agent!")
                    time.sleep(1)
                    st.rerun()
                elif res is None:
                     st.error("❌ Cannot connect to Backend API. Is it running?")
                else:
                    st.error("Failed to dispatch task.")

    with col2:
        st.subheader("Task Monitor")
        # Fetch tasks (Auto-refresh button)
        if st.button("🔄 Refresh Status"):
            clear_cache() # Force fetch new data
            st.rerun()
            
        try:
            # Use cached function
            tasks = get_tasks()
            if tasks:
                # Sort by created_at desc
                tasks.reverse()
                
                for task in tasks:
                    status_color = "gray"
                    if task['status'] == "completed":
                        status_color = "green"
                    elif task['status'] == "running":
                        status_color = "orange"
                    elif task['status'] == "failed":
                        status_color = "red"
                        
                    with st.container(border=True):
                        st.markdown(f"**{task['title']}** <span style='color:{status_color}; float:right'><b>{task['status'].upper()}</b></span>", unsafe_allow_html=True)
                        st.caption(f"ID: {task['id']} | Agent: {task['agent_id']}")
                        
                        if task['status'] == "completed":
                            st.markdown("---")
                            # Show file links
                            if task.get('output_files'):
                                for f_path in task['output_files']:
                                    st.write(f"📁 Generated: `{f_path}`")
                            # Show text preview
                            if task.get('output_text'):
                                st.text_area("Preview", task['output_text'], height=100, disabled=True)

                        if task['status'] == "failed":
                            st.error(task.get('output_text', 'Unknown Error'))

            else:
                st.write("Could not fetch tasks.")
        except Exception as e:
            st.error(f"Connection Error: {e}")

# --- Page: File Vault ---
elif page == "File Vault":
    st.header("📂 Company File Vault")
    
    OUTPUT_DIR = "outputs"
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    files = os.listdir(OUTPUT_DIR)
    
    if files:
        for file_name in files:
            file_path = os.path.join(OUTPUT_DIR, file_name)
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"📄 **{file_name}**")
                    st.caption(f"Path: {file_path}")
                with col2:
                    with open(file_path, "rb") as f:
                        st.download_button("Download", f, file_name=file_name)
                
                if file_name.endswith(".txt") or file_name.endswith(".md"):
                    with st.expander("Preview Content"):
                        with open(file_path, "r", encoding="utf-8") as f:
                            st.text(f.read())
    else:
        st.info("No files generated yet.")

# --- Page: Settings ---
elif page == "Settings":
    st.header("⚙️ System Configuration")
    
    st.info("Configure your LLM Provider here. Supports OpenAI, DeepSeek, or any OpenAI-compatible API.")
    
    with st.form("settings_form"):
        current_api_key = get_setting("api_key")
        current_base_url = get_setting("base_url")
        
        # Default Base URL if empty
        if not current_base_url:
            current_base_url = "https://api.openai.com/v1"
            
        api_key = st.text_input("API Key", value=current_api_key, type="password")
        base_url = st.text_input("Base URL", value=current_base_url, help="https://api.openai.com/v1 or https://api.deepseek.com/v1")
        
        submitted = st.form_submit_button("Save Settings")
        
        if submitted:
            s1 = save_setting("api_key", api_key)
            s2 = save_setting("base_url", base_url)
            if s1 and s2:
                st.success("Settings Saved!")
            else:
                st.error("Failed to save settings.")
