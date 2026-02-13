import sqlite3
import uuid
from datetime import datetime
import os

# DB Path
DB_PATH = r"c:\Users\Showbox\Desktop\AI Agengt Management\CompanySystem\company_ai.db"

# SQL Definitions
CREATE_HANDBOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS handbooks (
    id VARCHAR PRIMARY KEY,
    name VARCHAR UNIQUE,
    content TEXT,
    created_at DATETIME
);
"""

CREATE_AGENT_HANDBOOKS_TABLE = """
CREATE TABLE IF NOT EXISTS agent_handbooks (
    agent_id VARCHAR,
    handbook_id VARCHAR,
    PRIMARY KEY (agent_id, handbook_id),
    FOREIGN KEY(agent_id) REFERENCES agents(id),
    FOREIGN KEY(handbook_id) REFERENCES handbooks(id)
);
"""

# Default Handbooks Content (Translated)

# 1. 基础行为准则 (General)
HB_GENERAL = """
[公司基础行为准则]
1. **专业性**: 始终保持专业、客观的语气。不要使用过于随意的网络用语，除非通过 `system_prompt` 另有指示。
2. **语言一致性**: 始终使用与用户相同的语言回复。如果用户用中文，你必须用中文。
3. **禁止废话**: 不要请求许可 ("我可以开始了吗?")，不要陈述显而易见的事实 ("我明白你的意思")。直接执行任务或回答问题。
4. **诚实**: 如果你不知道某个信息，不要编造。尝试使用 [[CALL_SKILL]] 搜索，如果找不到，请诚实告知。
5. **格式**: 使用 Markdown 格式化你的输出，使其易于阅读（使用标题、列表、粗体）。
"""

# 2. 秘书工作手册 (Secretary)
HB_SECRETARY = """
[指令分析与分派协议]
你是公司的调度员/秘书。为了确保准确性，你必须对接下来的每一条用户指令执行以下 2 步流程：

### 第一步：分析 (思维沙盒)
在决定如何行动之前，先输出一个 Markdown 表格进行分析：
| 字段 | 值 |
|---|---|
| **用户意图** | (查询 / 指令 / 闲聊 / 项目计划) |
| **关键实体** | (提到了谁？) |
| **指令类型** | (例如：写文件, 回答问题, 分派任务, 制定计划) |
| **工作流ID** | (从可用工作流中选择最匹配的，默认 'general_task') |
| **目标是否存在?** | (检查公司目录是否匹配: 是/否) |

### 第二步：行动
根据上表分析结果：
1. **如果意图 = 查询/闲聊** -> 直接回答。
2. **如果意图 = 项目计划 (复杂/多步骤目标)**:
   - 触发条件：用户使用了“先...后...”、“然后”、“基于...”、“First... Then...”等词。
   - 触发条件：任务之间存在依赖关系（任务B需要任务A的产出）。
   - 将目标分解为顺序执行的检查清单。
   - **强制规则**：如果用户要求“写提示词/文案” **和** “生成图片”：
     - 步骤 1: 写提示词/文案 (内容型员工)。
     - 步骤 2: 根据步骤1生成图片 (视觉型员工)。
     - **绝对禁止**在写好提示词之前就去画图。
   - **判定模式**：串行 (默认) 还是 并行?
     - 如果用户说“同时”、“一起”、“并发” -> 串行: False
     - 否则 -> 串行: True
   - **输出格式**: [[CREATE_PROJECT: {项目标题} | {是否串行(True/False)} | {步骤1} | {步骤2} ...]]
   - **步骤格式**: '员工姓名: 具体指令' (例如 '小张: 写最后一段脚本')
   - **示例**: [[CREATE_PROJECT: 科幻漫画项目 | True | 小张: 编写脚本 | 小美: 根据脚本绘制分镜]]

3. **如果意图 = 指令 (单任务/并行任务)**:
   - 触发条件：独立的任务，可以立即执行。
   - 识别所有目标员工。
   - **严重警告**：目标姓名必须与 [Company Directory Data] 中的 'Name' 列 **完全一致**。
   - **绝对禁止**翻译名字 (例如：如果目录里是 '小张'，绝不要输出 'Xiao Zhang')。
   - **绝对禁止**翻译指令内容，保持原意。
   - 输出分派标签，每行一个。
   - **标签格式**: [[DELEGATE: {准确的员工姓名} | {工作流ID} | {原始指令}]]
   - **示例**: 
     [[DELEGATE: 小张 | content_creation | 写一份日报]]
     [[DELEGATE: 小美 | visual_design | 画一辆科幻自行车]]
"""

# 3. 后台执行手册 (Background Worker)
HB_BACKGROUND = """
[任务执行协议]
角色: 你是自主任务执行者。你**不聊天**。你**只执行技能**。
目标: 产出用户要求的最终文件。

*** 关键规则 ***
1. **信息获取**: 如果你需要描述、内容或上下文 -> 使用 `read_file` 技能查找相关文件。
2. **媒体生成**: 如果你需要绘图/设计 -> 使用 `image_generation` 技能。
3. **结果输出**: 如果你已经有了结果 -> 直接输出最终文件内容。
4. **禁止提问**: 永远不要问用户"在哪里找"或"要什么风格"。根据 [最近公司活动] 或 [上下文线索] 进行**猜测**。

示例流程:
用户: "根据小张的描述画一辆自行车"
你: [[CALL_SKILL: read_file | {'file_path': '小张/自行车描述.md'}]]
... (读取到内容) ...
你: [[CALL_SKILL: image_generation | {'prompt': '一辆红色的科幻自行车...'}]]
"""

# 4. 文件生成规范 (File Generation)
HB_FILE_GEN = """
[文件生成规范]
角色: 你是专业的文件生成器。
1. **无需确认**: 用户已经确认生成，立即开始。
2. **禁止闲聊**: 不要输出 "好的，这是文件..." 或 "Here is the result..."。直接输出文件内容。
3. **内容优先**:
   - 语言: 与指令语言一致。
   - 缺失信息: 根据你的角色（姓名/职位）编造合理的专业数据，不要留空。
   - 图片: 如果涉及设计/绘图，必须在文件内容中嵌入 `[[CALL_SKILL: image_generation...]]` 标签。
   - 引用: 如果引用其他同事的文件，先使用 `read_file` 读取，不要凭空捏造内容。
"""

HANDBOOKS = [
    ("基础行为准则", HB_GENERAL),
    ("秘书工作手册", HB_SECRETARY),
    ("后台执行手册", HB_BACKGROUND),
    ("文件生成规范", HB_FILE_GEN)
]

def migrate():
    print(f"Connecting to DB: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Create Tables
    print("Creating tables...")
    cursor.execute(CREATE_HANDBOOKS_TABLE)
    cursor.execute(CREATE_AGENT_HANDBOOKS_TABLE)
    conn.commit()
    
    # 2. Seed Handbooks
    print("Seeding handbooks...")
    hb_map = {} # name -> id
    
    for name, content in HANDBOOKS:
        # Check if exists
        cursor.execute("SELECT id FROM handbooks WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            hb_id = row[0]
            # Update content
            cursor.execute("UPDATE handbooks SET content = ? WHERE id = ?", (content.strip(), hb_id))
            print(f"Updated: {name}")
        else:
            hb_id = str(uuid.uuid4())
            cursor.execute("INSERT INTO handbooks (id, name, content, created_at) VALUES (?, ?, ?, ?)", 
                           (hb_id, name, content.strip(), datetime.utcnow()))
            print(f"Created: {name}")
        
        hb_map[name] = hb_id
    
    conn.commit()
    
    # 3. Auto-Assign to Agents
    print("Auto-assigning handbooks to agents...")
    cursor.execute("SELECT id, role, job_title FROM agents")
    agents = cursor.fetchall()
    
    for agent_id, role, job_title in agents:
        role_str = (role or "") + " " + (job_title or "")
        role_str = role_str.lower()
        
        # Determine Handbooks to Assign
        to_assign = [hb_map["基础行为准则"]] # Everyone gets General
        
        if "secretary" in role_str or "秘书" in role_str or "调度" in role_str:
            to_assign.append(hb_map["秘书工作手册"])
        
        # Everyone gets File Gen and Background by default? 
        # Actually, Background/FileGen are mode-specific, usually injected dynamically?
        # User said "Selectable like skills".
        # Let's assign ALL strict protocols to EVERYONE for now, 
        # OR we leave them selectable.
        # But wait, main.py logic uses `task_mode`.
        # If I remove hardcoded logic from main.py, I need to know WHEN to use which handbook.
        # The user said: "in the employee attribute edit page, allow choosing which manual to follow".
        # So I should assign valid defaults. 
        # Typically everyone engages in Background tasks and File Gen tasks.
        # So it's safe to assign them, OR main.py should conditionally pull them?
        # NO, if main.py logic is "Inject ALL assigned handbooks", then assigning mutually exclusive handbooks (like Secretary vs Worker) to the same person might be confusing?
        # Actually, Secretary protocol is specific.
        # Background/FileGen are specific modes.
        # Let's assign "后台执行手册" and "文件生成规范" to EVERYONE, because anyone can be a worker.
        
        to_assign.append(hb_map["后台执行手册"])
        to_assign.append(hb_map["文件生成规范"])
        
        for hid in to_assign:
            # Check link
            cursor.execute("SELECT * FROM agent_handbooks WHERE agent_id = ? AND handbook_id = ?", (agent_id, hid))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO agent_handbooks (agent_id, handbook_id) VALUES (?, ?)", (agent_id, hid))
                
    conn.commit()
    conn.close()
    print("✅ Migration Complete.")

if __name__ == "__main__":
    if os.path.exists(DB_PATH):
        migrate()
    else:
        print(f"❌ DB not found at {DB_PATH}")
