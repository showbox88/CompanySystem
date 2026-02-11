import streamlit as st
import requests
import time
import pandas as pd
import os

# Configuration
API_URL = "http://localhost:8000"

LEVEL_OPTIONS = [
    "Junior (初级)",
    "Senior (资深)",
    "Manager (经理)",
    "Director (总监)",
    "VP (副总裁)",
    "C-Level (高管)"
]

st.set_page_config(page_title="AI Agent Company System", layout="wide")

st.title("🏭 AI Agent Company Management System")

# Sidebar Navigation
# Default to High-Level Meeting Room for testing convenience
page = st.sidebar.radio("Navigation", ["High-Level Meeting Room", "Agent Center", "Task Console", "File Vault", "Settings"])

# --- Helper Functions (Optimized) ---
# Create a persistent session to speed up connections
if 'api_session' not in st.session_state:
    st.session_state['api_session'] = requests.Session()

def make_request(method, endpoint, **kwargs):
    """Unified request handler with session"""
    url = f"{API_URL}{endpoint}"
    response = None
    try:
        if method == "GET":
            response = st.session_state['api_session'].get(url, **kwargs)
        elif method == "POST":
            response = st.session_state['api_session'].post(url, **kwargs)
        elif method == "PUT":
            response = st.session_state['api_session'].put(url, **kwargs)
        elif method == "DELETE":
            response = st.session_state['api_session'].delete(url, **kwargs)
        return response
    except requests.exceptions.ConnectionError:
        return None

# Use caching to avoid fetching data on every UI interaction
@st.cache_data(ttl=2)
def get_agents():
    try:
        response = requests.get(f"{API_URL}/agents/")
        if response.status_code == 200:
            data = response.json()
            # print(f"DEBUG: Agents loaded: {[a['name'] for a in data]}") 
            return data
    except:
        return []
    return []

# Initialize Meeting State (Moved here to access get_agents)
if 'meeting_participants' not in st.session_state:
    st.session_state['meeting_participants'] = set()
    # Auto-add Secretary (Xiao Fang) for convenience
    all_agents = get_agents()
    secretary = next((a for a in all_agents if "Secretary" in a['role'] or "秘书" in a['role']), None)
    if secretary:
        st.session_state['meeting_participants'].add(secretary['id'])

if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []

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

def create_agent(name, role, system_prompt, job_title="", department="", level=""):
    payload = {
        "name": name,
        "role": role,
        "job_title": job_title,
        "department": department,
        "level": level,
        "system_prompt": system_prompt,
        "model_name": "gpt-4-turbo",
        "temperature": 0.7
    }
    res = make_request("POST", "/agents/", json=payload)
    if res and res.status_code == 200:
        clear_cache() # Force refresh
    return res

def update_agent_details(agent_id, name, role, system_prompt, job_title, department, level):
    payload = {
        "name": name,
        "role": role,
        "job_title": job_title,
        "department": department,
        "level": level,
        "system_prompt": system_prompt
    }
    res = make_request("PUT", f"/agents/{agent_id}", json=payload)
    if res and res.status_code == 200:
        clear_cache()
    if res and res.status_code == 200:
        clear_cache()
    return res

def stream_chat_message(agent_id, message, force_execution=False):
    """Sends chat message to backend and yields streaming response."""
    
    # Build history from session state
    history_payload = []
    if 'chat_history' in st.session_state:
        # Exclude the last item which is likely the current user prompt 
        # (Since we append it right before calling this)
        raw_history = st.session_state['chat_history'][:-1] if st.session_state['chat_history'] else []
        
        for msg in raw_history:
            # Only keep essential fields
            history_payload.append({
                "role": msg["role"],
                "content": msg["content"],
                "name": msg.get("name")
            })

    payload = {
        "agent_id": agent_id,
        "message": message,
        "history": history_payload,
        "force_execution": force_execution
    }
    
    # We use requests directly here for streaming support
    import requests
    import json
    
    url = f"{API_URL}/chat/"
    try:
        with requests.post(url, json=payload, stream=True, timeout=60) as response:
            if response.status_code == 200:
                # Use iter_content for raw streaming capability (more robust than iter_lines for non-SSE)
                for chunk in response.iter_content(chunk_size=None):
                    if chunk:
                        yield chunk.decode('utf-8')
            else:
                yield f"Error: {response.status_code}"
    except Exception as e:
        yield f"Error: {str(e)}"

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
            
            c1, c2, c3 = st.columns(3)
            with c1:
                new_title = st.text_input("Job Title", placeholder="e.g. Manager")
            with c2:
                new_dept = st.text_input("Department", placeholder="e.g. Sales")
            with c3:
                new_level = st.selectbox("Level", LEVEL_OPTIONS, index=0)

            new_prompt = st.text_area("System Prompt", placeholder="You are an expert in...", height=150)
            submitted = st.form_submit_button("Create Agent")
            
            if submitted:
                if new_name and new_role and new_prompt:
                    res = create_agent(new_name, new_role, new_prompt, new_title, new_dept, new_level)
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
                    # View Mode
                    if not st.session_state.get(f"edit_mode_{agent['id']}", False):
                        st.write(f"**ID:** `{agent['id']}`")
                        st.write(f"**Title:** {agent.get('job_title', '-')} | **Dept:** {agent.get('department', '-')} | **Level:** {agent.get('level', '-')}")
                        st.markdown(f"**System Prompt:**\n> {agent['system_prompt']}")
                        
                        c1, c2 = st.columns([1, 1])
                        with c1:
                            if st.button("Edit Agent", key=f"btn_edit_{agent['id']}"):
                                st.session_state[f"edit_mode_{agent['id']}"] = True
                                st.rerun()
                        with c2:
                            if st.button("Delete Agent", key=f"del_{agent['id']}"):
                                make_request("DELETE", f"/agents/{agent['id']}")
                                clear_cache()
                                st.rerun()
                    
                    # Edit Mode
                    else:
                        with st.form(f"edit_form_{agent['id']}"):
                            e_name = st.text_input("Name", value=agent['name'])
                            e_role = st.text_input("Role", value=agent['role'])
                            
                            c1, c2, c3 = st.columns(3)
                            with c1:
                                e_title = st.text_input("Job Title", value=agent.get('job_title', ''))
                            with c2:
                                e_dept = st.text_input("Department", value=agent.get('department', ''))
                            with c3:
                                current_level = agent.get('level', LEVEL_OPTIONS[0])
                                # Handle case where current level is not in options (e.g. legacy data)
                                idx = 0
                                if current_level in LEVEL_OPTIONS:
                                    idx = LEVEL_OPTIONS.index(current_level)
                                e_level = st.selectbox("Level", LEVEL_OPTIONS, index=idx)
                                
                            e_prompt = st.text_area("System Prompt", value=agent['system_prompt'], height=150)
                            
                            saved = st.form_submit_button("Save Changes")
                            if saved:
                                res = update_agent_details(agent['id'], e_name, e_role, e_prompt, e_title, e_dept, e_level)
                                if res:
                                    st.success("Updated!")
                                    st.session_state[f"edit_mode_{agent['id']}"] = False
                                    st.rerun()
                                else:
                                    st.error("Update failed.")
                            
                            if st.form_submit_button("Cancel"):
                                st.session_state[f"edit_mode_{agent['id']}"] = False
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
                                st.text_area("Preview", task['output_text'], height=100, disabled=True, key=f"preview_{task['id']}")

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

# --- Page: High-Level Meeting Room ---
elif page == "High-Level Meeting Room":
    st.header("👔 High-Level Meeting Room (高层会议室)")
    st.write("Select one or more management levels to enter this exclusive meeting room.")
    
    # 1. Levels Filter (Multiselect)
    # Default selection: Manager and above
    default_levels = [l for l in LEVEL_OPTIONS if "Manager" in l or "Director" in l or "VP" in l or "C-Level" in l]
    selected_levels = st.multiselect("Select Levels to Admit:", LEVEL_OPTIONS, default=default_levels)
    
    # 2. Filter Agents
    agents = get_agents()
    qualified_agents = []
    
    if agents:
        for agent in agents:
            # Check if agent level is in selected levels
            # Handle potential None values or case sensitivity if needed
            a_level = agent.get('level', '')
            if a_level and a_level in selected_levels:
                qualified_agents.append(agent)
    
    if qualified_agents:
        st.success(f"Found {len(qualified_agents)} qualified agents.")
        
        # --- Participants Management ---
        st.subheader("👥 Meeting Participants (参会人员)")
        
        # Display current participants
        if st.session_state['meeting_participants']:
            cols = st.columns(4)
            for idx, p_id in enumerate(list(st.session_state['meeting_participants'])):
                # Find agent name
                p_agent = next((a for a in agents if a['id'] == p_id), None)
                if p_agent:
                    with cols[idx % 4]:
                        st.info(f"{p_agent['name']}")
                        if st.button("Kick Out", key=f"kick_{p_id}"):
                            st.session_state['meeting_participants'].remove(p_id)
                            st.rerun()
        else:
            st.caption("No agents in the meeting room yet.")
            
        st.divider()

        # --- Available Agents & Chat Interface ---
        col_list, col_chat = st.columns([1, 2])
        
        with col_list:
            st.subheader("Available Options")
            for agent in qualified_agents:
                with st.container(border=True):
                    st.write(f"**{agent['name']}**")
                    st.caption(f"{agent.get('job_title', 'N/A')} - {agent.get('level', 'N/A')}")
                    
                    if agent['id'] not in st.session_state['meeting_participants']:
                        if st.button("Invite ➕", key=f"invite_{agent['id']}"):
                            st.session_state['meeting_participants'].add(agent['id'])
                            st.rerun()
                    else:
                        st.button("Joined ✅", key=f"joined_{agent['id']}", disabled=True)

        with col_chat:
            st.subheader("💬 Meeting Chat")
            chat_container = st.container(height=500)
            
            # Display Chat History
            for msg in st.session_state['chat_history']:
                with chat_container:
                    with st.chat_message(msg["role"], avatar=msg.get("avatar")):
                        st.write(f"**{msg['name']}**: {msg['content']}")
            
            # Chat Input
            if prompt := st.chat_input("Say something to the meeting..."):
                # 1. Add User Message
                st.session_state['chat_history'].append({
                    "role": "user",
                    "name": "User",
                    "content": prompt,
                    "avatar": "👤"
                })
                
                # Show user message immediately
                with chat_container:
                     with st.chat_message("user", avatar="👤"):
                        st.write(f"**User**: {prompt}")

            # --- Decision Logging ---
            with st.expander("📝 Record a Decision (记录决策)", expanded=False):
                decision_text = st.text_input("Decision Content:", key="decision_input")
                if st.button("Save to Log"):
                    if decision_text:
                        payload = {
                            "agent_id": None, # User decision
                            "event_type": "DECISION",
                            "content": decision_text
                        }
                        res = make_request("POST", "/logs/decision", json=payload)
                        if res and res.status_code == 200:
                            st.success("Decision recorded!")
                        else:
                            st.error("Failed to record decision.")
                    else:
                        st.warning("Please enter content.")
                
            if prompt: # Continue with chat logic if prompt exists (moved from above)
                # 3. Get Responses from All Participants
                if st.session_state['meeting_participants']:
                    # Determine target agents (Selective Replying)
                    target_p_ids = []
                    
                    # Check if any agent name is mentioned
                    mentioned = False
                    participants_objects = []
                    for p_id in st.session_state['meeting_participants']:
                        p_agent = next((a for a in agents if a['id'] == p_id), None)
                        if p_agent:
                            participants_objects.append(p_agent)
                            if p_agent['name'] in prompt:
                                target_p_ids.append(p_id)
                                mentioned = True
                    
                    # If no one is mentioned, everyone replies
                    if not mentioned:
                        target_p_ids = list(st.session_state['meeting_participants'])
                        
                    # Create a container for new messages
                    with chat_container:
                        for p_id in target_p_ids:
                            p_agent = next((a for a in agents if a['id'] == p_id), None)
                            if p_agent:
                                with st.chat_message("assistant", avatar=p_agent.get("avatar") or "🤖"):
                                    st.write(f"**{p_agent['name']}**")
                                    # Streaming Output with Placeholder
                                    message_placeholder = st.empty()
                                    full_response = ""
                                    
                                    # Stream and Accumulate
                                    for chunk in stream_chat_message(p_id, prompt):
                                        full_response += chunk
                                        # Optional: Check for tag early to stop streaming if needed, 
                                        # but typically tag comes at the end or is the whole message.
                                        message_placeholder.markdown(full_response + "▌")
                                    
                                    # Final processing
                                    delegate_match = None
                                    if "[[EXECUTE_TASK:" in full_response:
                                        # (Existing EXECUTE_TASK logic)
                                        import re
                                        match = re.search(r"\[\[EXECUTE_TASK:\s*(.*?)\s*\|", full_response)
                                        task_title = match.group(1) if match else "Task"
                                        display_text = f"🚀 **Task Started:** {task_title}\n\nCheck your 'Company Doc' folder shortly."
                                        message_placeholder.markdown(display_text)
                                        full_response = display_text
                                    
                                    elif "[[DELEGATE:" in full_response:
                                        import re
                                        # Use finditer to find ALL delegations
                                        d_matches = list(re.finditer(r"\[\[DELEGATE:\s*(.*?)\s*\|\s*(.*?)\]\]", full_response, re.DOTALL))
                                        
                                        if d_matches:
                                            display_text_parts = []
                                            delegate_list = []
                                            
                                            for d_match in d_matches:
                                                target_name = d_match.group(1).strip()
                                                instruction = d_match.group(2).strip()
                                                display_text_parts.append(f"📣 **Delegating to:** `{target_name}`\n> {instruction}")
                                                delegate_list.append((target_name, instruction))
                                            
                                            display_text = "\n\n".join(display_text_parts)
                                            message_placeholder.markdown(display_text)
                                            full_response = display_text # Hide raw tags
                                            
                                            # Store list of delegations
                                            delegate_match = delegate_list 
                                        else:
                                             message_placeholder.markdown(full_response)
                                             delegate_match = None

                                    else:
                                        message_placeholder.markdown(full_response)
                                        delegate_match = None
                                    
                                    # Save to History
                                    st.session_state['chat_history'].append({
                                        "role": "assistant",
                                        "name": p_agent['name'],
                                        "content": full_response,
                                        "avatar": p_agent.get("avatar") or "🤖"
                                    })
                                    
                                    # Handle Delegation (Chained Execution)
                                    if delegate_match and isinstance(delegate_match, list):
                                        # FORCE REFRESH AGENTS to ensure we have latest data
                                        current_agents = get_agents() # This uses cache, but we'll try to rely on it first.
                                        # If needed we could force clear_cache(), but let's try robust matching first.
                                        
                                        def find_agent_by_name(name, agent_list):
                                            name = name.strip()
                                            for a in agent_list:
                                                a_name = a['name'].strip()
                                                # 1. Exact Match (Case Insensitive)
                                                if name.lower() == a_name.lower():
                                                    return a
                                                # 2. Name contained in Agent Name (e.g. "Xiao Ming" in "Mr. Xiao Ming")
                                                if name in a_name or a_name in name:
                                                    return a
                                                # 3. Job Title Match
                                                if a.get('job_title') and name in a['job_title']:
                                                    return a
                                            return None

                                        for target_name, instruction in delegate_match:
                                            # Find Target Agent using Helper
                                            target_agent = find_agent_by_name(target_name, current_agents)
                                            
                                            if target_agent:
                                                with chat_container:
                                                    # Use a distinct UI for remote execution
                                                    with st.chat_message("assistant", avatar=target_agent.get("avatar") or "🤖"):
                                                        # Determine label
                                                        is_in_meeting = target_agent['id'] in st.session_state['meeting_participants']
                                                        status_label = "Delegated" if is_in_meeting else "Remote Execution (远程执行)"
                                                        
                                                        st.write(f"**{target_agent['name']}** - *{status_label}*")
                                                        
                                                        # Delegate Prompt with FORCED EXECUTION instruction
                                                        delegated_prompt = (
                                                            f"Source: Delegated by {p_agent['name']}.\n"
                                                            f"Task: {instruction}\n"
                                                            f"CRITICAL: Execute this task acting as YOURSELF ({target_agent['name']}). Do not write about the sender.\n\n"
                                                            "SYSTEM COMMAND: This is a delegated task. "
                                                            "1. If this involves writing/generating a document/code/file, you MUST use the file generation protocol.\n"
                                                            "2. OUTPUT IMMEDIATELY: [[EXECUTE_TASK: {Title} | {Content}]]\n"
                                                            "3. DO NOT ASK FOR CONFIRMATION. DO NOT JUST CHAT.\n"
                                                            "4. Just output the tag."
                                                        )
                                                        
                                                        # Stream Response
                                                        d_message_placeholder = st.empty()
                                                        d_full_response = ""
                                                        
                                                        # Call stream_chat_message with force_execution=True
                                                        # Note: recursive call might re-trigger this if not careful, but force_execution=True usually prevents delegation tags.
                                                        for d_chunk in stream_chat_message(target_agent['id'], delegated_prompt, force_execution=True):
                                                            d_full_response += d_chunk
                                                            d_message_placeholder.markdown(d_full_response + "▌")
                                                        
                                                        # Check for Task execution
                                                        if "[[EXECUTE_TASK:" in d_full_response:
                                                              import re
                                                              match = re.search(r"\[\[EXECUTE_TASK:\s*(.*?)\s*\|", d_full_response)
                                                              task_title = match.group(1) if match else "Task"
                                                              d_text = f"🚀 **Remote Task Started:** {task_title}\n\nCheck your 'Company Doc' folder shortly."
                                                              d_message_placeholder.markdown(d_text)
                                                              d_full_response = d_text
                                                        else:
                                                              d_message_placeholder.markdown(d_full_response)
                                                        
                                                        st.session_state['chat_history'].append({
                                                            "role": "assistant",
                                                            "name": target_agent['name'],
                                                            "content": d_full_response,
                                                            "avatar": target_agent.get("avatar") or "🤖"
                                                        })
                                            else:
                                                st.error(f"Could not find agent matching '{target_name}' to delegate to.")
                                                # Debug info is good, keeping it invisible to user unless error
                                                # print(f"DEBUG: Failed to find agent '{target_name}'. Available: {[a['name'] for a in current_agents]}")

                else:
                    st.warning("No agents in the meeting to reply!")
                    # st.rerun()

            # Auto-Focus Hack
            import streamlit.components.v1 as components
            components.html(
                """
                <script>
                var input = window.parent.document.querySelector("textarea[data-testid='stChatInputTextArea']");
                if (input) {
                    input.focus();
                }
                </script>
                """,
                height=0, width=0
            )
    else:
        st.warning("No agents found with the selected levels.")

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
