# Changelog

All notable changes to the **AI Company System** project will be documented in this file.

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
