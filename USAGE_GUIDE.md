# NeuroCortex 使用指南

## 快速开始

### 1. 启动服务（端口 9100）

```bash
# 进入目录
cd /workspace/neuro-cortex

# 启动（默认配置，全部功能关闭）
python3 server.py

# 开启 Action Learning（实验模式）
NEUROCORTEX_ACTION_LEARNING=true python3 server.py

# 开启 Policy Shadow（只观察不干预）
NEUROCORTEX_POLICY_ENABLED=true python3 server.py
```

### 2. 发送消息

```bash
# HTTP POST
curl -X POST http://localhost:9100/chat \
  -H "Content-Type: application/json" \
  -d '{"msg": "帮我检查一下代码"}'

# 返回示例：
# {"intent": "review", "probability": 0.75, "response": "..."}
```

### 3. 使用封装脚本

```bash
# Python 工具
python3 tools/neurocortex.py analyze "帮我写个测试"

# Bash 工具
bash tools/call_neurocortex.sh "帮我检查代码"

# Wrapper（带人格保存）
bash tools/nc-wrapper.sh "今天的任务是..."
```

### 4. 人格管理

```bash
# 查看当前人格状态
python3 tools/neurocortex.py personality

# 保存人格到文件（含 Tick 动态更新）
python3 tools/neurocortex.py save
```

---

## 核心概念

```
你的消息
    ↓
BilingualPerception（意图识别）
    → explain / create / fix / review / deploy / optimize / test / general
    ↓
Representation + Memory（检索相关经验）
    ↓
Prediction（经验预测，权重 0.3）
    ↓
Decision（基于 INTENT_ACTION_MAP 选择动作）
    ↓
Action（执行动作）
    ↓
Outcome（记录结果）
    ↓
Learning（写入 ~/.neurocortex_memory.jsonl）
```

---

## 实验功能开关

通过环境变量控制，默认全部关闭：

| 环境变量 | 作用 | 实验阶段 |
|---------|------|---------|
| `NEUROCORTEX_ACTION_LEARNING=true` | 启用真实执行 Bridge | Level 4.x |
| `ACTION_LEARNING_SHADOW_ONLY=true` | Shadow 模式（只记录不改行为） | NC-08B |
| `NEUROCORTEX_POLICY_ENABLED=true` | 启用 Policy Engine | Level 6.x |
| `NC05B_ENABLED=true` | 多动作策略验证 | NC-05B |
| `NC06_ENABLED=true` | 受控策略对比实验 | NC-06 |
| `NC06_NC_RATIO=0.2` | NC 流量占比（默认 20%） | NC-06 |

---

## 数据存储位置

| 路径 | 内容 |
|------|------|
| `~/.neurocortex_memory.jsonl` | 经验库（每次对话自动写入） |
| `~/.neurocortex_action_statistics.json` | 动作统计 |
| `~/.neurocortex_observation_log.jsonl` | 观察日志（NC-08A.3+） |
| `neuro-cortex/experiments/nc08b/shadow/shadow_log.jsonl` | Shadow 观测日志 |
| `neuro-cortex/experiments/nc08b/real_completion_observations.jsonl` | 真实完成观测 |

---

## 一句话总结

> **NeuroCortex 是一个持续学习的对话代理核心**。你只需要 `python3 server.py` 启动服务，然后用 curl 或脚本发请求，它就会在每次对话中积累、检索经验，逐步优化决策。
> 所有实验功能通过环境变量开启，默认是稳定模式。
