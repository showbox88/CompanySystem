# Changelog

All notable changes to the **AI Company System** project will be documented in this file.

## [v1.4.0] - 2026-02-13
### 🌟 Major Features (重大更新)
- **Employee Handbook System (员工手册系统)**:
    - **Database-Driven Prompts**: Replaced hardcoded system instructions with dynamic `Handbooks` stored in the database.
    - **Flexible Assignment**: Agents can now be assigned multiple Handbooks (e.g., "General Conduct" + "Secretary Manual") via the UI.
    - **Role-Specific Logic**: Handbooks for "Secretary", "Background Worker", and "File Generation" are automatically injected based on context.
    - **Migration Script**: Added `scripts/migrate_handbooks.py` to auto-seed default Chinese handbooks.

### 🐛 Bug Fixes (修复)
- **Gemini Integration**:
    - **Provider Fix**: Corrected `provider` mismatch for agents (e.g., 'Xiao Zhi') causing 404 errors.
    - **History Handling**: Fixed `AttributeError: 'dict' object has no attribute 'role'` when processing chat history during retries.
    - **Generator Consumption**: Fixed `TypeError` when `call_llm_service` returned a generator object instead of a string in non-streaming mode.
    - **Image Gen Billing**: Verified and documented that Gemini Imagen 3/4 requires Google Cloud Billing; added fallback guidance to OpenAI.

## [v1.3.0] - 2026-02-13
### 🌟 Major Features (重大更新)
- **Project Management System (项目管理系统)**:
    - **Concept**: Introduced "Project Files" (`Project_...md`) as the central context for multi-agent collaboration.
    - **Context Awareness**: Agents automatically read the most recent project file (even if created by others) to maintain continuity.
    - **Smart Name Matching**: Implemented fallback strategies to handle agent name mismatches (e.g., "Xiao Zhang" vs "小张") by looking at recent project activity.
- **Standalone Image Generation (独立生图)**:
    - **Robustness**: Fixed JSON parsing to support single-quoted arguments common in LLM outputs.
    - **Markdown Capture**: Enhanced `main.py` to capture images returned as Markdown tags (`![...](...)`), not just specific strings.
    - **Local Storage**: Images are automatically downloaded to `Company Doc/{Agent}/assets/` and linked in the generated Markdown file.

### 🛠️ Improvements & Fixes (改进与修复)
- **Smart Completion**: Relaxed "Short Response" error triggers. Agents are no longer punished for saying "Done" if they have successfully performed a skill (e.g., generated an image).
- **Loop Prevention**: Enhanced loop detection with context-aware guidance (e.g., "You already read the file, move on").
- **Asset Persistence**: Fixed bug where generated images were lost if the agent didn't explicitly list them in the final text.
- **Skill Loader**: Fixed `IndentationError` in `builtins.py` that prevented skills from loading.

## [v1.2.0] - 2026-02-12
### 🌟 Major Features (重大更新)
- **AI Skill System (技能系统)**:
    - **Architecture**: Implemented `SkillRegistry`, `SkillDispatcher`, and `AgentSkill` database mapping.
    - **Image Generation**: Agents can now design images (using DALL-E 3) via `[[CALL_SKILL: image_generation]]`.
    - **File Access**: Agents can read internal documents via `[[CALL_SKILL: read_file]]`.
- **Multi-Turn Reasoning Engine (多步思考引擎)**:
    - Background tasks now support a **Think-Act-Observe-Act** loop (up to 5 turns).
    - Enables complex workflows like "Read Requirements -> Design Image -> Write Report".
- **Enhanced Awareness (增强感知)**:
    - **Log Injection**: Agents now directly read `Company_Log.md` to spot new files from colleagues.
    - **Auto-Discovery**: `read_file` skill automatically searches subdirectories if the exact path is unknown.

### 🛠️ Improvements & Fixes (改进与修复)
- **Robustness**:
    - **Fuzzy Skill Dispatching**: Corrects hallucinated skill names (e.g. `image_gen` -> `image_generation`).
    - **Loose Argument Parsing**: Supports JS-style objects and unquoted keys.
    - **Argument Aliasing**: `description` maps to `prompt`, `filename` maps to `file_path`.
- **Backend Stability**:
    - Fixed `IndentationError` in `main.py` causing crashes.
    - Fixed `TypeError` in history processing for Pydantic/Dict compatibility.
    - Fixed `BASE_DIR` calculation logic for accurate file path resolution.

## [v1.1.0] - 2026-02-11
### 🚀 New Features (新特性)
- **Mental Sandbox (思维沙箱)**: 
    - Secretary (Xiao Fang) now performs a structured "Command Analysis" before dispatching tasks.
    - Displays a thought process table (Intent, Entities, Validation) to the user.
- **Smart Delegation (智能派发)**: 
    - Support for delegating tasks to specific agents via natural language (e.g., "Let Xiao Ming write a report").
    - **Fuzzy Matching**: Enhanced agent name recognition (handles spaces, case sensitivity, and job titles).
- **Multi-Agent Meeting Room**:
    - dedicated chat interface for multi-agent collaboration.
    - Auto-add Secretary to meeting on startup.
- **Zero-Shot Dispatch Mode**:
    - Backend now uses a strict "Dispatch Mode" that ignores chat history to prevent agent hallucination during task execution.
- **Auto-Focus**: Chat input box automatically gathers focus on page load.
- **Company Directory Injection**: Agents now obey the official company directory for name/role lookups.

### 🐛 Bug Fixes (修复)
- **Identity Crisis**: Fixed issue where delegated agents would write about the *sender* instead of themselves.
- **Language Consistency**: Fixed Chat Mode confirmation messages defaulting to English (now matches user language).
- **Thread Safety**: Fixed race conditions in background task processing (`SessionLocal` per thread).
- **Agent Recognition**: Fixed "Xiao Ming not found" error caused by encoding/whitespace issues.
- **Over-Scrupulosity**: Fixed Secretary delegating tasks when user was merely asking a question (Intent Recognition added).

## [v1.0.0] - 2026-02-01
### Initial Release
- Basic Agent Management (CRUD).
- Task execution and file generation.
- Streamlit Frontend & FastAPI Backend.
- SQLite Database integration.
