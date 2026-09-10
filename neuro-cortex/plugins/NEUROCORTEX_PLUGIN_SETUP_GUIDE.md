# NeuroCortex Plugin — 配置与部署指导

> 适用版本: neurocortex-plugin v2.1.0
> 仓库位置: `https://github.com/wbdyouxiang2023-gif/agent-autonomous`
> 插件路径: `neuro-cortex/plugins/neurocortex-plugin/`

---

## 一、目录结构

```
neurocortex-plugin/
├── __init__.py              # Hermes 插件入口 (register + hooks)
├── plugin.yaml              # 插件清单 (Hermes 加载用)
├── server.py                # NC 9100 认知服务 (独立进程)
├── shadow_observer.py       # Shadow 模式观察器
├── nc05b_shadow_observer.py # NC-05B 影子观察器
├── nc06_controlled_trial.py # NC-06 受控试验
├── experiment/
│   ├── __init__.py
│   └── observation_logger.py # 观测日志写入 ~/.nc_observations.jsonl
└── src/neurocortex/          # 核心认知系统 (自包含, 不依赖外部)
    ├── cortex.py            # NeuroCortex 主类
    ├── action_learning/     # 动作学习引擎
    ├── decision/            # 决策模块
    ├── perception/          # 感知/意图分类
    ├── memory/              # 经验存储/检索
    ├── prediction/          # 结果预测
    ├── policy/              # 策略引擎
    ├── pattern/             # 模式整合
    ├── feedback/            # 反馈
    └── state/               # 认知状态
```

**关键特性**: 插件是**自包含**的 —— `src/` 在插件目录内，不依赖仓库其他部分。

---

## 二、安装到 Hermes

### 1. 放置插件目录

```bash
# 从仓库克隆或下载后
cp -r neuro-cortex/plugins/neurocortex-plugin/ ~/.hermes/plugins/
```

### 2. 确认 Hermes 启用插件

编辑 `~/.hermes/config.yaml`，确保:

```yaml
plugins:
  enabled:
    - neurocortex-plugin
```

### 3. 验证插件加载

```bash
hermes plugins list | grep neurocortex
# 期望输出: neurocortex-plugin │ enabled │ 2.1.0 │ ... │ user
```

---

## 三、启动 NC 9100 服务

插件依赖独立运行的 `server.py`（认知服务，端口 9100）。

### 手动启动

```bash
cd ~/.hermes/plugins/neurocortex-plugin/
python3 server.py
# 期望输出:
#   Loading NeuroCortex, experience store: ~/.neurocortex_memory.jsonl
#   Loaded N experiences. Ready on port 9100.
```

### 作为后台服务（推荐）

```bash
nohup python3 server.py > /tmp/nc_server.log 2>&1 &
```

### 验证服务

```bash
curl http://localhost:9100/health
# 期望: {"status": "ok", "experiences": N}
```

---

## 四、环境变量配置（可选）

| 变量 | 默认 | 说明 |
|---|---|---|
| `NEUROCORTEX_ACTION_LEARNING` | `false` | 动作学习总开关 (`true` 开启) |
| `ACTION_LEARNING_SHADOW_ONLY` | `true` | Shadow 模式（只观察不干预） |
| `NEUROCORTEX_POLICY_ENABLED` | `false` | 策略引擎开关 |
| `NEUROCORTEX_POLICY_SHADOW_ONLY` | `true` | 策略 Shadow 模式 |
| `NC05B_ENABLED` | `false` | NC-05B 影子观察器 |
| `NC06_ENABLED` | `false` | NC-06 受控试验 |
| `NC_SHADOW_MODE` | `off` | NC-08B Shadow 推荐模式 |

示例（启用 Shadow 学习）:

```bash
export NEUROCORTEX_ACTION_LEARNING=true
export ACTION_LEARNING_SHADOW_ONLY=true
python3 server.py
```

---

## 五、与 Hermes 的集成链路

```
Hermes Gateway
  ↓ (每轮 LLM 调用前)
pre_llm_call hook → on_pre_llm()
  ↓ HTTP POST
localhost:9100/chat  {"msg": "用户消息"}
  ↓ NC 处理
返回 {"intent", "probability", "experience_count", ...}
  ↓
on_pre_llm 组装 "[NeuroCortex auto-analysis] intent=... confidence=... experiences=..."
  ↓ 注入用户消息
LLM 请求 (context 进入 prompt)
  ↓ (每次工具调用后)
post_tool_call hook → on_tool_call()
  ↓
record_experience() → ~/.neurocortex_experiences.jsonl
```

---

## 六、数据文件（运行时生成）

| 文件 | 用途 |
|---|---|
| `~/.neurocortex_memory.jsonl` | 认知记忆存储 |
| `~/.neurocortex_experiences.jsonl` | 工具调用经验记录 |
| `~/.nc_observations.jsonl` | /chat 观测日志 |
| `~/.persona.json` | 人格状态 |
| `~/.neurocortex_action_statistics.json` | 动作学习统计 |
| `~/.neurocortex_shadow_log.jsonl` | Shadow 观察日志 |

---

## 七、故障排查

| 症状 | 检查 |
|---|---|
| 插件未加载 | `hermes plugins list` 看 enabled；`config.yaml` 的 plugins.enabled |
| 9100 连不上 | `curl localhost:9100/health`；`ps aux \| grep server.py` |
| 无 NC context 注入 | agent.log 搜 `initialized successfully`；确认 server.py 在跑 |
| post_tool_call 无记录 | 检查 `~/.neurocortex_experiences.jsonl` 是否更新 |
| Hook 未注册 | gateway.log 搜 `hook registered`（INFO 级） |

---

## 八、NC-09 冻结约束

⚠️ **重要**:
- NC-09 Learning Core（`src/neurocortex/`）**已冻结**
- 禁止修改学习算法、Shadow Mode、决策逻辑
- 禁止进入 NC-10
- 本次上传即收口版本，后续仅允许 bug 修复（不改核心行为）

---

*配置指导生成时间: 2026-09-10*
