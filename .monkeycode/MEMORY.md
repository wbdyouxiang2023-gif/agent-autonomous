# User Instruction Memory

This file records user instructions, preferences, and teachings for reference in future interactions.

## Format

### User Instruction Entry
User instruction entries should follow this format:

[User Instruction Summary]
- Date: [YYYY-MM-DD]
- Context: [Mentioned scenario or time]
- Instructions:
  - [Content of user teaching or instruction, described line by line]

### Project Knowledge Entry
Entries discovered by the Agent during task execution should follow this format:

[Project Knowledge Summary]
- Date: [YYYY-MM-DD]
- Context: Discovered by Agent while performing [specific task description]
- Category: [Operations & Deployment|Build Methods|Testing Methods|Troubleshooting & Debugging|Workflow & Collaboration|Environment Configuration]
- Instructions:
  - [Specific knowledge points, described line by line]

## Deduplication Strategy
- Before adding a new entry, check for similar or identical instructions.
- If a duplicate is found, skip the new entry or merge it with the existing one.
- When merging, update the context or date information.
- This helps avoid redundant entries and keeps the memory file tidy.

## Entries

[Project Knowledge Summary]
- Date: 2026-09-06
- Context: 搭建 Agent 工作台，初始化 autonomous agent 系统
- Category: Build Methods
- Instructions:
  - Go CLI 编译: `go build -o /workspace/todos ./src/todos.go`
  - Python 测试: `python3 /workspace/tests/test_agent.py`
  - 启动 Dashboard: `python3 app.py`（端口 7860）
  - Gradio 6.0+ 的 theme 参数需传入 launch()，不能放在 Blocks 构造函数中

[Project Knowledge Summary]
- Date: 2025-09-04
- Context: 完成自主运行系统搭建并推送到 GitHub
- Category: Operations & Deployment
- Instructions:
  - GitHub 用户: wbdyouxiang2023-gif
  - 仓库: https://github.com/wbdyouxiang2023-gif/agent-autonomous
  - 本地预览: https://7860-b0ecdb9061e08fd2.monkeycode-ai.online
  - GitHub secret scanning 会阻止含 token 的提交，必须使用 gitignore 排除
