# NeuroCortex 版本路线图

> 生成时间：2026-09-09
> 当前 HEAD：14ecde4 feat: NC-08C.0 policy permission architecture
> 总提交数：66
> 分支：main（活跃）、new-main（实验）、origin/master（旧主线）

---

## 一、阶段总览

```
v0.x (初始代理)  ──→  Phase 0-3 (基础模块)  ──→  Phase 4-7 (核心模块)
    └─ Go CLI + Gradio                    └─ Perception/Representation/Prediction/Decision
         ↓                                    ↓
Phase 8-10 (学习闭环)  ──→  Phase 11-13 (知识层)  ──→  Level 4.x-5.x (Action Learning)
    └─ Action module + L3 loop            └─ Experience abstraction / Pattern consolidation
         ↓                                    ↓
Level 6.x (Policy Trial)  ──→  Level 7.x (Policy Disagreement)  ──→  Level 8.x (Real-World Validation)
    └─ NC-05/06 controlled trials           └─ NC-07A/B natural disagreement
         ↓                                    ↓
                              Level 8.x → NC-08A/B/C (Data → Shadow → Permission)
```

---

## 二、详细版本历史

### v0.1 — 初始代理系统（Commit 1-7）

| 提交 | 内容 |
|------|------|
| `52ae49d` | Initial commit — 项目骨架 |
| `701f5df` | chore: 初始化项目结构 |
| `88a6edf` | feat: Go CLI todo app + JSON persistence |
| `7434d36` | feat: 能力探索器与环境脚本 |
| `4d2f55d` | docs: 状态文档 |
| `037090b` | feat: 环境验证脚本 |
| `b5f022d` | test: TodoStore 单元测试 |
| `2c0e406` | docs: 架构文档 |
| `f07f26b` | fix: Store 方法指针接收者修复 |
| `da4b424` | fix: todo ID 从 1 开始初始化 |
| `c816ac3` | fix: 测试初始化对齐 |
| `754c456` | feat: Go Web Server + Dashboard + REST API |
| `e4b9bdb` | docs: README 更新 |
| `3064fe8` | feat: Gradio Web 界面（HF Spaces 部署） |
| `284f5e7` | feat: 自主代理系统（目标生成 + 持久记忆） |
| `fa812e9` | feat: 完整自主代理系统 |

**关键产物**：Go CLI todo、Gradio dashboard、REST API。

---

### v0.2 — 工作区搭建（Commit 8-12）

| 提交 | 内容 |
|------|------|
| `fd63159` | feat: Go CLI + Python tests + Gradio dashboard 工作区 |
| `f98d04f` | fix: Gradio theme 移动到 launch()，重建 CLI |
| `bd81a33` | docs: 工作区构建笔记 |
| `2cf2251` | feat: AI personality + 自主决策引擎 + digital creator 模块 |
| `b84fdcc` | refactor: 持久化人格状态，接入决策引擎 |
| `63e42a7` | docs: 优化发现写入 memory |
| `116ba03` | chore: Phase 0 项目骨架 |
| `01faadd` | chore: Phase 0 目录结构与测试 |

**关键产物**：人格系统、决策引擎框架、经验存储结构。

---

### Phase 1-3 — 基础模块实现（Commit 13-19）

| 版本 | 提交 | 内容 |
|------|------|------|
| Phase 0 | `116ba03` | 项目骨架 + 目录结构 |
| Phase 1 | `789b380` | CortexEvent 统一数据结构（typed nested stages） |
| Phase 1.1 | `b3f77a3` | Outcome 与 Feedback 分离，澄清 state 约束 |
| Phase 2 | `c0189ca` | NeuroCortex 编排层 + 模块接口 |
| Phase 2.1 | `16001ee` | 严格 Action/Outcome 分离 + OutcomeProvider |
| Phase 3 | `1ff8797` | Perception + Representation 模块 |
| — | `eecdc25` | Perception 中文 keyword 支持扩展 |

**关键产物**：
- `CortexEvent` 统一事件流
- `Perception` 双语感知模块
- `Representation` 状态表示模块
- 模块接口标准化

---

### Phase 4-7 — 核心模块完善（Commit 20-27）

| 版本 | 提交 | 内容 |
|------|------|------|
| Phase 4 | — | Attention + Memory 模块（集成已有组件） |
| Phase 5 | `50656ca` | Prediction 模块实现 |
| Phase 6 | `078f8fc` | Feedback 评估冻结 |
| Phase 6+7 | `fb230ef` | 架构审计 spec（Phase 6+7 文档） |
| Phase 7 | `546b42e` | 确定性 Decision 模块实现 |

**关键产物**：
- `ExperiencePredictionModule` — 基于经验的预测
- `BasicDecision` — 确定性决策（INTENT_ACTION_MAP 映射）
- `PersistentOutcome` — 持久化结果提供者

---

### Phase 8-10 — 学习闭环验证（Commit 28-33）

| 版本 | 提交 | 内容 |
|------|------|------|
| Phase 8 | `00ac18f` | Action 模块实现 |
| Phase 9 | `9e2e176` | 跨事件学习闭环验证 |
| Phase 10 | `b3ab0c8` | 自适应行为验证 |

**关键发现**：
- 学习闭环存在断点：经验被保存但权重过低（Evidence Weight = 0.3）
- Pattern Store 文件不存在，Pattern 未激活
- MCP Server 未运行，降级到本地模式

---

### Phase 11-13 — 知识层演进（Commit 34-41）

| 版本 | 提交 | 内容 |
|------|------|------|
| Phase 11 | `98dfcea` | Experience Abstraction MVP |
| Phase 12 | `adc8cbe` | Pattern Consolidation：Experience → Pattern → Prediction |
| Phase 12 fix | `3ce854e` | 消除证据双重计数（bounded adjustment） |
| — | `252afac` | Evidence Integrity Implementation Report |
| Phase 13 | `9cadbd4` | Knowledge Architecture Audit |
| Phase 13.5 | `8b3a4e7` | Semantic Generalization 架构审计 |
| Phase 13 knowledge | `b0f02b0` | Knowledge Layer 架构审计 |
| Level 3 audit | `acc27b7` | Capability & Goal Audit（NeuroCortex at Level 3） |

**关键产物**：
- `PatternConsolidationModule` — 经验抽象与模式提取
- `WeightSweepCounterfactual` — 权重扫描实验
- Learning Loop Repair Audit v1（诊断学习闭环断点）

---

### Level 4.x — Action Learning 引入（Commit 42-45）

| 版本 | 提交 | 内容 |
|------|------|------|
| Level 4.0 | `c2b4de4` | Action Learning + Real Execution Bridge |
| — | `3b9894d` | server.py minimal Action Learning hook（默认关闭） |
| Level 4.3 | `9e8e489` | Policy Learning 层 |

**关键架构**：
- `ActionLearningEngine` — 从真实执行中学习
- `ExecutionBridge` — 决策 → 真实 Hermes 工具 → 真实结果
- `RealExecutionOutcomeProvider` — 真实执行结果适配器
- 默认关闭（`REAL_EXECUTION_BRIDGE_ENABLED=false`）

---

### Level 5.x — Situation & Intent（Commit 46-51）

| 版本 | 提交 | 内容 |
|------|------|------|
| Level 5.0-R1 | `a4d7e93` | IntentExtractor — rule-based 任务意图提取 |
| — | `572f511` | IntentExtractor empty-JSON path 修复 |
| Level 5.0-R2 | `a7cbc10` | Plugin R2 — IntentExtractor 集成 |
| Level 5.1 | `3bdec56` | Situation Similarity & Evidence Transfer |
| — | `46fc360` | neuron.py CLI with --intent support |

**关键产物**：
- `IntentExtractor` — 从原始输入提取任务意图
- `SituationSimilarity` — 场景相似度计算
- `SemanticTransfer` — 证据语义迁移

---

### Level 6.x — Policy Trial（Commit 52-59）

| 版本 | 提交 | 内容 |
|------|------|------|
| R4-R5 | `9821668` | Shadow Learning + PolicyEngine 集成 |
| NC-05B | `d45e66f` | Multi-Action Policy Validation |
| NC-06 | `da68196` | Controlled Policy Trial v0.1 |
| NC-06.1 | `44fd2a3` | Policy Disagreement Validation — NO_NATURAL_POLICY_DISAGREEMENT |
| NC-06.2 | `9a3bce0` | Evidence Isolation Audit — CONTEXTUAL_EVIDENCE_ISOLATION_BLOCKED |
| NC-06.2 fix | `0e17430` | Evidence Scope Isolation — L1 beats L3 |
| NC-06.3 | `59fd241` | Natural Policy Disagreement Re-validation（expected negative） |
| NC-06.4 | `ab3463e` | Action Space Independence — CANDIDATE_SPACE_LIMITED |
| NC-06.5 | `0cf8a87` | Independent Candidate Generation — VALIDATED |

**关键发现**：
- 候选空间受限，NC 无法产生与 Original 本质不同的候选
- Evidence Isolation 存在上下文污染，L1（低）> L3（高）排序正确性依赖
- NC-06.5 独立候选生成验证通过

---

### Level 7.x — Natural Disagreement（Commit 60-65）

| 版本 | 提交 | 内容 |
|------|------|------|
| NC-07A | `bfbe8a7` | Natural Disagreement Collection — NO_YET（首次） |
| NC-07A | `6a4aaa8` | Natural Disagreement Collection — NO_YET（重复验证） |
| NC-07A bug | `579b9ad` | Ranking Sort Override Score Bug |
| NC-07A-R1 | `bb0a067` | Ranking Fix + **NATURAL_DISAGREEMENT_DETECTED**（首次真实分歧） |
| NC-07B-A | `b60c80d` | Controlled Policy Outcome Trial — NO_VALIDATED_POLICY_SUPERIORITY |
| NC-07B-A v2 | `2fed732` | Controlled Policy Outcome Trial v2 — Ineffective NC |
| NC-07B-C | `a30b9d0` | Outcome Utility Audit — LEARNING_OBJECTIVE_MISALIGNED |

**关键突破**（NC-07A-R1）：
- 修复 Ranking 排序逻辑（`has_evidence, -level` → `score` only）
- 102 个任务中发现 12 个（11.8%）Natural Disagreement
- Optimize intent 下 NC 选择 respond（L3）vs tool_call（L1）

---

### Level 8.x — Real-World Validation（Commit 66-75）

| 版本 | 提交 | 内容 |
|------|------|------|
| NC-08A audit | `2f22458` | Outcome Schema Upgrade — TASK_COMPLETION_SOURCE_MISSING |
| NC-08A feat | `2ea9379` | Outcome Schema 升级 — task_completion 字段 |
| NC-08A.1 | `f89af62` | Data Provenance — No Real task_completion Data |
| NC-08A.2 | `6df1c91` | Real Task Completion Signal Integration — READY_FOR_REAL_OBSERVATION |
| NC-08A.3 | `2c3fcee` | Real Completion Observation Collection — 32 observations |
| NC-08A final | `ed24652` | NC-08 series 完整数据报告 |
| NC-08A fix | `4881e9a` | OutcomeData.from_dict 回归修复 |
| NC-08B.1 | — | Completion Ranking Collector v1 |
| NC-08B.2 | — | Ranking Validation |
| NC-08B.3 | `077ab29` | Completion Ranking Live Shadow Deployment（已接 WSL remote） |
| NC-08C.0 | `14ecde4` | Policy Permission Architecture（当前 HEAD） |

**关键产物**：
- `task_completion` 字段加入 Outcome Schema
- 130 条真实观察数据（experiment/FINAL_REPORT.md）
- Shadow 模式接入 WSL remote Hermes server
- Policy Selector 三层安全门控（kill switch → mode → assignment → gates）

---

## 三、当前架构状态

```
Branch: main (14ecde4)
Test:   597 passed, 8 skipped, 13 failed (预存 regression 问题)

Core Modules (src/neurocortex/):
  perception/     — 双语感知
  representation/ — 状态表示（mock）
  attention/      — 注意力（mock）
  state/          — 基本状态模块
  memory/         — 经验检索（mock）
  prediction/     — 经验预测模块
  decision/       — 基础决策（INTENT_ACTION_MAP）
  action/         — 基础动作执行
  outcome/        — 持久化结果
  feedback/       — 反馈计算（mock）
  learning/       — 经验学习模块

New Modules (action_learning/):
  engine/         — ActionLearningEngine
  intent_extractor/ — IntentExtractor
  similarity/     — SituationSimilarity
  semantic_transfer/ — SemanticTransfer
  bridge/         — ExecutionBridge
  outcome/        — ExecutionLog, RealExecutionOutcomeProvider

Experiment Modules (experiments/):
  nc08b/          — Shadow Observer + Ranking Collector
  nc08c/          — PolicySelector（权限架构）
```

---

## 四、已知问题

| 问题 | 影响 | 状态 |
|------|------|------|
| `tools.file_tools` 不可用 | ExecutionBridge 5 个测试失败 | 已知，bridge 设计为 fail-soft |
| Regression 测试路径硬编码 | 8 个 regression 测试在 workspace root 外失败 | 需修复路径或使用 PYTHONPATH |
| Pattern Store 文件不存在 | Pattern 未激活，权重仅 0.3 | Level 3.5 审计已确认 |
| MCP Server 未运行 | 降级到本地模式 | 运行时配置问题 |

---

## 五、下一步方向（基于审计结论）

1. **Level 3.5 Learning Loop Repair** — 修复 Evidence Weight 过低问题
2. **NC-08C.1** — Shadow 模式下线，进入 trial_nc 模式
3. **Level 9.x** — 基于 130 条真实观察数据训练 Policy
4. **Pattern Store 激活** — 将 Experience 提取为可复用 Pattern
5. **Regression 测试修复** — 修正路径硬编码问题
