# NC-08B.3 — Live Shadow Architecture Audit

**Date:** 2026-09-09
**Type:** Read-only architecture audit — no code modified, no wiring, no live shadow

---

## 一、真实调用链（server.py）

```
POST /chat
  └─ cortex.process(msg)                        ← ORIGINAL POLICY 决策
       └─ event.decision.selected_action        ← Original Action（Executor 输入）
  ├─ log_observation(event, msg)                ← try/except: pass
  ├─ shadow_observer.observe_decision(event,msg)← try/except: pass (shadow, 只记录)
  │    └─ Shadow Learning Observer (shadow_observer.py:72)
  │         "Does NOT modify event or affect execution"（源码注释）
  ├─ NC-06 controlled trial (默认 OFF)          ← 既有代码，非 NC-08B.3
  │    └─ 仅当 NC06_ENABLED=true 才可能改 selected_action
  └─ resp["action"] = event.decision.selected_action  ← Executor 收到的最终 Action

Shadow Adapter（NC-08B.3，未接入 server）:
  experiments/nc08b/shadow/shadow_adapter.py
  └─ recommend() → nc_recommended_action → shadow_log.jsonl（独立日志）
```

```
CALL_CHAIN_CONFIRMED = YES
```

## 二、NC 是否可能影响 Actual Action

全仓搜索 `nc_recommended_action` / `nc_action` / `recommendation` / `shadow` / `NC_SHADOW_MODE`：

- **server.py 未引用 shadow_adapter**（grep 无匹配）——NC-08B.3 的 NC 推荐**完全无法进入** server 决策链
- 唯一 NC→action 赋值：`server.py:228 event.decision.selected_action = nc06_result["final_action"]`——这是**既有 NC-06 受控试验**（`NC06_ENABLED` 默认 false，非 NC-08B.3 代码）
- **不存在** `if nc...: action = nc...` / `action = nc_action or original_action` / `if confidence: action = nc_action` 等模式

```
NC_CAN_CHANGE_ACTUAL_ACTION = NO（NC-08B.3 代码）
NC_CAN_REACH_EXECUTOR      = NO（adapter 未被 server import）
```

## 三、Executor 输入来源

```
EXECUTOR_ACTION_SOURCE = ORIGINAL_POLICY
  server.py:206 cortex.process(msg) → BasicDecision._decide()
  server.py:240 resp["action"] = event.decision.selected_action
  唯一可能改写：NC-06（默认 OFF，既有代码，非本次 Shadow Adapter）
```

## 四、ShadowAdapter 能力边界

`shadow_adapter.py` 全部方法：`_load_evidence` / `_completion_rate` / `rank_by_completion` / `recommend` / `_log` / `make_adapter`

- **无** execute / dispatch / run_action / apply_policy
- **无** subprocess / os.system / Popen
- **纯推荐 + 记录**：输入 situation+candidates → 输出 ranking + 写独立 log

```
SHADOW_CAPABILITY_BOUNDARY = PASS（pure recommendation/evaluation）
```

## 五、Feature Flag

```
NC_SHADOW_MODE 仅在 experiments/nc08b/shadow/ 内引用（adapter.py:27 + eval.py:30）
server.py 不读取该 flag —— 与生产完全隔离

OFF（默认）: recommend() → None，零副作用（已验证：无 log 追加）
ON:         只增加 recommendation + ranking + shadow log
             不改变 actual_action（assert rec["original_action"] == original_action）

FEATURE_FLAG_SAFE = YES
```

## 六、Outcome 来源

```
TASK_COMPLETION_SOURCE = event.outcome.task_completed（真实执行后的 OutcomeData）
  event.py:179 task_completed: bool|None = None  # None = unknown, 非 False
  event.py:180 completion_source: str = "unknown"（provenance 追踪）
  schema.py:111 outcome_from_event() — 从 event.outcome.task_completed 提取
  "NEVER fabricates task_completion from action_type"（源码注释）
  无 execution_success → task_completion 推导（已验证）

OUTCOME_SOURCE_VALID = YES
```

## 七、数据隔离

```
Shadow Log:  experiments/nc08b/shadow/shadow_log.jsonl（独立）
Production:  ~/.neurocortex_experiences.jsonl（插件写，未触碰）
NC-08B 130 observations: 只读（MD5 验证未变）
  real_completion_observations.jsonl  4c99f3a3...
  situation_observations.jsonl        fdba4395...

DATA_ISOLATION_VALID = YES
```

## 八、并发/异常安全

```
server.py:210-217:
  event = cortex.process(msg)          ← Original 决策在 shadow 之前，独立完成
  try:
      shadow_result = shadow_observer.observe_decision(event, msg)
  except Exception as _e:
      pass                              ← NC shadow 失败被吞，不影响 response
  NC-06 同理 try/except: pass

NC_FAILURE_BLOCKS_ORIGINAL = NO（shadow 异常被捕获忽略）
```

## 九、性能影响

```
Original decision（cortex.process）先于 shadow 执行，不等待 NC 计算
shadow 在决策后异步观察（同线程但 try/except 包裹，失败即跳过）
NC 超时/异常 → Original Action 不受影响

SHADOW_BLOCKS_ORIGINAL = NO
```

## 十、日志结构

Shadow record 字段（实测 30 条）：
```
timestamp ✓  task_id ✓  situation ✓  candidate_actions ✓
original_action ✓  nc_recommended_action ✓  nc_ranking ✓  nc_scores ✓
original_completion_rate ✓  model_version ✓  shadow_only=True ✓
```
**⚠️ 缺失字段**（审计发现，接线时应补充）：
- `actual_action`（当前由 original_action 隐含，未显式记录）
- `task_completion` / `completion_source`（adapter 决策时 outcome 未产生——合理，但完成 shadow 链路后应回填）
- `original_ranking`（当前只记 nc_ranking，未记 original 的 ranking）

```
SHADOW_LOG_ISOLATED = YES
```

## 十一、最终安全判定

```
CALL_CHAIN_CONFIRMED           = YES
ORIGINAL_POLICY_SOURCE         = cortex.process → BasicDecision._decide()
EXECUTOR_ACTION_SOURCE         = ORIGINAL_POLICY
NC_CAN_CHANGE_ACTUAL_ACTION    = NO
NC_CAN_REACH_EXECUTOR          = NO
SHADOW_CAPABILITY_BOUNDARY     = PASS
FEATURE_FLAG_SAFE              = YES
OUTCOME_SOURCE_VALID           = YES
DATA_ISOLATION_VALID           = YES
NC_FAILURE_BLOCKS_ORIGINAL     = NO
SHADOW_BLOCKS_ORIGINAL         = NO
SHADOW_LOG_ISOLATED            = YES

PRODUCTION_POLICY_CHANGED      = NO（本次未改任何代码）
REAL_ACTION_EXECUTED_BY_NC     = NO
HISTORICAL_DATA_MODIFIED       = NO

ARCHITECTURE_VERDICT = SAFE_TO_WIRE
```

### 判定依据

Shadow Adapter 满足严格 shadow-only 架构：
1. 纯推荐（无执行能力）+ 独立日志 + 独立 flag
2. server.py 完全未引用——**当前零风险**（甚至还没接入）
3. 既有的 shadow_observer.observe_decision 也严格只读（try/except 包裹）
4. NC-06（唯一能改 action 的 NC 代码）默认 OFF，且不属于 NC-08B.3

### 接线前建议（非阻塞，报告用）
1. shadow record 补充 `actual_action` / `task_completion` / `completion_source` / `original_ranking` 字段（回填链路）
2. 在 server.py 的 observe_decision 旁增加 adapter 调用点（同样 try/except 包裹）
3. 明确 NC-06 与 NC-08B.3 的 flag 边界（NC06_ENABLED vs NC_SHADOW_MODE）
