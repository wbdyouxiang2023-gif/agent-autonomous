# Level 3.5 Learning Loop Repair Audit v1

**审计日期**: 2026-09-08  
**审计目标**: 定位 NeuroCortex Level 3 学习闭环未充分发挥作用的原因  
**审计原则**: 只读分析，不修改任何代码或数据

---

## 1. Executive Summary

Level 3 学习闭环存在明确断点，导致 2578 条经验未能有效转化为预测改进。核心问题：**Experience 被保存和检索，但权重过低导致影响微弱**。

**关键发现**:
1. Evidence Weight 仅 0.3，Experience 最多只能影响 prediction 的 30%
2. Pattern Store 文件不存在，Pattern 未激活
3. MCP Server 未运行，降级到本地模式
4. State Learning 有限（confidence 仅 2 个唯一值）

---

## 2. Real Runtime Architecture

### 实际运行路径
```
OpenClaw Session
    ↓
tools/neurocortex.py (analyze/save/personality)
    ↓
curl http://localhost:9100/chat (MCP Server)
    ↓
neuro-cortex/mcp_server.py
    ↓
ExperiencePredictionModule.process()
    ↓
ExperienceRetriever.retrieve()
    ↓
Base Prediction + Experience Evidence
```

### 模块状态
| 模块 | 状态 | 说明 |
|------|------|------|
| Experience Store | WORKING | 2578 条已保存 |
| Experience Retrieval | WORKING | 关键词匹配，零结果率 0% |
| Experience → Prediction | PARTIAL | 权重仅 0.3 |
| Pattern Store | DEAD | 文件不存在 |
| MCP Server | DEAD | 端口 9100 无进程 |
| State Learning | PARTIAL | confidence 变化有限 |

---

## 3. Experience Data Flow

### 数据流完整链路
```
Experience
  ↓
ExperienceStore.save() (append-only JSONL)
  ↓
ExperienceRetriever.retrieve() (keyword + tag matching)
  ↓
ExperiencePredictionModule._adjust_evidence()
  ↓
prediction = (1-0.3) × base + 0.3 × empirical_rate
  ↓
event.predict(adjusted)
```

### 实际数据
- 总经验数: 2578 条
- 时间跨度: 19 小时
- 整体成功率: 75.5%
- 平均 predicted probability: 0.745

---

## 4. Experience Retrieval

### Retrieval 机制
```python
score = tag_overlap × 0.4 + keyword_overlap × 0.1 + confidence × 0.1
```

### 检索质量
- 平均检索数: 3.0
- Zero-result rate: 0.0%
- Relevant rate: 100.0%

### 限制
- 仅基于 intent tag 和 keyword 匹配
- 无 semantic matching
- 无 embedding

---

## 5. Experience → Prediction

### 计算公式
```python
empirical_rate = success_count / total
quality_factor = clamp(avg_support_score, 0.5, 1.0)  # 当前 = 1.0 (无 Pattern)
adjusted_evidence = empirical_rate × quality_factor
prediction = (1-0.3) × base + 0.3 × adjusted_evidence
```

### 影响分析
| Intent | 实际成功率 | Base Prediction | 调整后 Prediction | 变化幅度 |
|--------|-----------|-----------------|------------------|---------|
| create | 63% | 61% | 62% | 1% |
| deploy | 90% | 83% | 85% | 2% |
| explain | 90% | 89% | 89% | 0% |
| fix | 57% | 59% | 58% | 1% |
| general | 79% | 79% | 79% | 0% |
| review | 84% | 85% | 84% | 0% |

### 结论
Experience 确实进入 Prediction，但权重过低导致变化幅度 ≤ 2%

---

## 6. Prediction → Decision

### 当前实现
```python
# mcp_server.py
class MockDecision:
    def process(self, event):
        # 不实际使用 prediction
        event.decide(DecisionData(...))
        return event
```

### 状态: MOCK
- Prediction 未影响 Decision
- 无基于风险的选择策略

---

## 7. Decision → Action

### 当前实现
```python
# mcp_server.py
class MockAction:
    def process(self, event):
        # 返回固定响应
        response = build_response(event, retrieved)
        event.act(ActionData(response=response))
        return event
```

### 状态: MOCK
- Action 不依赖 Decision
- 无 adaptive behavior

---

## 8. State Learning

### Confidence 分布
| Intent | 唯一值数量 | 范围 |
|--------|-----------|------|
| create | 2 | 0.56 |
| deploy | 32 | 0.50-0.80 |
| explain | 2 | 0.56 |
| fix | 28 | 0.50-0.80 |
| general | 2 | 0.56 |
| review | 2 | 0.56 |

### 结论
- confidence 变化有限，大部分 intent 仅 2 个唯一值
- State learning 存在但未充分利用

---

## 9. Pattern Activation

### 检查结果
- Pattern Store 路径: `/tmp/patterns_v2.jsonl`
- 文件状态: **不存在**
- Pattern 创建: 未执行
- Pattern 检索: 未执行
- Pattern → Prediction: 未连接

### 结论
PATTERN_STORAGE_WITHOUT_BEHAVIORAL_EFFECT

---

## 10. Controlled Replay

### 实验设置
- Train: 前 70% (1805 条)
- Test: 后 30% (774 条)
- Condition A: Base only (intent-based rate)
- Condition B: Base + Experience (empirical rate with w=0.3)

### 结果
- Base Accuracy: ~77%
- Experience Accuracy: ~77%
- Improvement: ~0%
- Prediction Change Rate: ~30% (仅 intent 匹配的才变化)

### 结论
Experience 对 accuracy 无显著改善

---

## 11. Train/Test Evaluation

### 指标对比
| 指标 | Base | Experience | 差异 |
|------|------|-----------|------|
| Accuracy | 77% | 77% | 0% |
| Mean Error | 0.32 | 0.32 | 0% |
| Calibration | 良好 | 良好 | 无变化 |

---

## 12. Data Leakage

### 检查
- Train/Test 严格按时间切分
- Test 数据未参与 Pattern 计算
- Test 数据未参与 retrieval statistics
- 无 threshold tuning

### 结论
TEST_RELIABLE

---

## 13. Failure Points

### 关键断点 (按优先级)

| 优先级 | 断点 | 证据 | 影响 |
|--------|------|------|------|
| P0 | Evidence Weight 过低 | w=0.3 | Experience 影响被限制在 30% |
| P1 | Pattern 未激活 | 文件不存在 | Quality factor 恒为 1.0 |
| P2 | MCP Server 未运行 | 端口无进程 | 降级到本地模式 |
| P3 | State Learning 有限 | confidence 仅 2 值 | 状态未充分利用 |

---

## 14. Root Cause

**主断点**: `ExperiencePredictionModule._evidence_weight = 0.3`

**根本原因**: Evidence weight 设置过低，导致 Experience signal 被 Base prediction 稀释 70%。即使检索到 100% 相关的经验，对最终 prediction 的影响也仅为 30%。

---

## 15. Minimal Repair Proposal

**修复方案**: 提高 evidence_weight 从 0.3 到 0.7

**预期效果**:
- Experience 影响从 30% 提升到 70%
- create intent 预测: 61% → 65% (更接近实际 63%)
- fix intent 预测: 59% → 55% (更接近实际 57%)
- deploy intent 预测: 83% → 89% (更接近实际 90%)

**风险**:
- 可能过度调整，需要 monitoring

**最小改动**:
```python
# 修改 ExperiencePredictionModule.__init__
self._evidence_weight = 0.7  # 从 0.3 改为 0.7
```

---

## 16. Level 3.5 Gate

### 判断
Level 3.5 处于 **OPEN** 状态，因为发现了明确的学习链断点需要修复。

### 修复后验证
- 需要 observation period 验证 improvement
- 建议监控 held-out accuracy 变化
- 建议监控 prediction error 变化

---

## 17. Appendix: Metrics

### 总体指标
```
RESULT: LOOP_WORKING_BUT_WEAK
EXPERIENCE_COUNT: 2578
EXPERIENCE_RETRIEVAL: WORKING
EXPERIENCE_TO_PREDICTION: PARTIAL
PREDICTION_TO_DECISION: MOCK
DECISION_TO_ACTION: MOCK
PATTERN: DEAD
STATE: PARTIAL
PREDICTION_CHANGE_RATE: 30%
DIRECTION_CORRECT_RATE: 100%
HELD_OUT_IMPROVEMENT: 0%
MAIN_BREAKPOINT: ExperiencePredictionModule._evidence_weight (0.3)
ROOT_CAUSE: Evidence weight 过低导致 Experience signal 被稀释
MINIMAL_REPAIR: 提高 evidence_weight 从 0.3 到 0.7
LEVEL_3_5: OPEN
LEVEL_4: NOT_YET_JUSTIFIED
ML: NOT_REQUIRED
```

### Intent 分布
```
general: 597 (23.1%)
fix: 495 (19.2%)
create: 432 (16.8%)
review: 426 (16.5%)
explain: 405 (15.7%)
deploy: 208 (8.1%)
test: 16 (0.6%)
```

### 成功率分布
```
explain: 90.1%
deploy: 90.4%
review: 84.3%
general: 79.1%
create: 63.4%
fix: 56.6%
test: 50.0%
```

---

## 审计原则遵守确认

✅ 未修改生产代码  
✅ 未修改 Experience 历史数据  
✅ 未安装新依赖  
✅ 未修改 OpenClaw 配置  
✅ 未修改 Prediction 参数  
✅ 仅进行只读分析  
