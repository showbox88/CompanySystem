# AI Agent Company System (AI 员工管理系统)

这是一个基于 **Python + FastAPI + Streamlit** 构建的 AI Agent 编排与管理平台。
它允许你像经营公司一样，招聘不同角色的 AI 员工 (Agents)，为它们定义人设 (System Prompts)，并下达任务 (Tasks) 产出实际的工作成果。

## 📚 文档 (Documentation)

*   **[📝 更新日志 (CHANGELOG)](CHANGELOG.md)**: 查看版本迭代与修复记录。
*   **[🏗️ 系统架构 (Structure)](STRUCTURE.md)**: 了解系统的底层逻辑与工作流。

## 🎯 核心设计理念

本系统旨在探索 **"AI Agent as a Workforce" (AI 即劳动力)** 的概念：
1.  **Mental Sandbox (思维沙箱)**: 秘书 (Dispatcher) 在执行命令前会先进行结构化分析，拒绝模糊指令。
2.  **Zero-Shot Dispatch (零样本派发)**: 后台强制执行模式，消除聊天历史对任务执行的干扰。
3.  **Result-Oriented**: 一切以产出为导向，所有任务最终都会在 `Company Doc` 文件夹中生成实体文件。

## 📂 项目结构

```
/Company System
├── /Company Doc             # [核心] AI 员工产出的所有工作文件 (按名字归档)
├── /backend                 # 后端服务 (FastAPI + SQLite)
├── frontend_app.py          # 前端控制台 (Streamlit)
├── CHANGELOG.md             # 更新日志
├── STRUCTURE.md             # 架构说明
└── ...
```

## 🚀 快速开始

### 1. 启动系统
双击 **`run_system.bat`**。
*   自动配置 Python 虚拟环境。
*   自动启动 API 服务 (Port 8000) 和 前端页面 (Port 8501)。

### 2. 开始工作
1.  在 **Settings** 配置 API Key。
2.  在 **Agent Center** 招聘员工 (或使用默认员工)。
3.  进入 **Meeting Room**，直接对秘书下达指令：
    *   *"让小美设计一个Logo"*
    *   *"让小张写一份营销策划"*
4.  检查 **`Company Doc`** 文件夹，查看他们交付的工作成果。

## 🛠️ 技术栈

*   **Runtime**: Python 3.8+
*   **Backend**: FastAPI, SQLAlchemy
*   **Frontend**: Streamlit
*   **Orchestration**: Custom "Mental Sandbox" Protocol

## 📝 许可证
MIT License
