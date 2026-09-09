# NeuroCortex Level 3.5-B
# Weight Sweep + Counterfactual Learning Validation v1

**实验日期**: 2026-09-08  
**实验类型**: 只读离线验证  
**严格规则**: 无修改、无安装、无提交

---

## 1. RESULT

```
RESULT: NO_VALIDATED_LEARNING_SIGNAL
```

**核心发现**: 模型已内化经验，Experience 不提供额外信号。

---

## 2. EXPERIENCE_COUNT

```
EXPERIENCE_COUNT: 2582
时间范围: 2026-09-07T14:34:54 至 2026-09-08T11:52:56
成功率: 75.5% (1949/2582)
意图分布: general(600), fix(495), create(432), review(426), explain(405), deploy(208), test(16)
数据质量: 零缺失、零重复、完整性100%
```

---

## 3. TRAIN_COUNT

```
TRAIN_COUNT: 1807 (前70%)
Train成功率: 74.5%
Intent分布: general(362), fix(315), create(319), review(305), explain(304), deploy(202)
```

---

## 4. HOLDOUT_COUNT

```
HOLDOUT_COUNT: 775 (后30%)
Test成功率: 77.8%
Intent分布: general(238), fix(180), create(113), review(121), explain(101), test(16), deploy(6)
分布偏移: +3.3% (test > train)
```

---

## 5. DATA_LEAKAGE

```
DATA_LEAKAGE: NONE
EXPERIMENT_VALID: TRUE
```

**检查项**:
- [x] TEST Experience 未进入 retrieval
- [x] TEST outcome 未进入任何 rate
- [x] TEST 未进入 Pattern
- [x] Weight selection 使用离线比较
- [x] 无未来时间戳泄漏
- [x] Empirical rates 仅从 TRAIN 计算

---

## 6. BASELINE (GROUP A)

```
Group A: BASE (intent-based prediction)
  Accuracy:    0.778
  MAE:         0.359
  Brier:       0.174
  Calibration: 0.075
  HighConfFail: 0.036
```

---

## 7. BASE + EXPERIENCE (GROUP B)

```
Group B: BASE + EXPERIENCE (w=0.3)
  Accuracy:    0.778 (Δ=0.000)
  MAE:         0.359 (Δ=0.000)
  Brier:       0.174 (Δ=0.000)
  RealAlign:   0.079
  ChangeRate:  0.000
```

**关键发现**: Experience 未改变任何 prediction。

---

## 8. BASE + PATTERN (GROUP C)

```
Group C: BASE + PATTERN
  PATTERN_RUNTIME_STATUS: DEAD
  Pattern Store: /tmp/patterns_v2.jsonl NOT FOUND
  Pattern Code: Not initialized in mcp_server.py
  Contribution: NONE
```

---

## 9. BASE + EXPERIENCE + PATTERN (GROUP D)

```
Group D: Combined
  Accuracy:    0.778 (无改善)
  Improvement: 0.000
  Note: Pattern inactive, Experience provides no signal
```

---

## 10. WEIGHT SWEEP

| Weight | Accuracy | MAE | Brier | HighConfFailure |
|--------|----------|-----|-------|-----------------|
| 0.0 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 0.1 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 0.2 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 0.3 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 0.4 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 0.5 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 0.6 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 0.7 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 0.8 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 0.9 | 0.7781 | 0.3592 | 0.1744 | 0.036 |
| 1.0 | 0.7781 | 0.3592 | 0.1744 | 0.036 |

**结论**: 所有权重产生相同结果，因为 base 和 experience 是同一值。

---

## 11. INTENT BREAKDOWN

| Intent | Base Acc | Exp Acc | Delta | Samples |
|--------|----------|---------|-------|---------|
| create | 0.726 | 0.726 | 0.000 | 113 |
| deploy | 0.500 | 0.500 | 0.000 | 6 |
| explain | 0.901 | 0.901 | 0.000 | 101 |
| fix | 0.672 | 0.672 | 0.000 | 180 |
| general | 0.807 | 0.807 | 0.000 | 238 |
| review | 0.876 | 0.876 | 0.000 | 121 |
| test | 0.500 | 0.500 | 0.000 | 16 |

---

## 12. EXPERIENCE REAL ALIGNMENT

```
REAL_PREDICTION_IMPROVEMENT_RATE: 0.079 (7.9%)
PREDICTION_CHANGE_RATE: 0.000%
DIRECTION_CORRECT_RATE: 0.079 (7.9%)
```

**解释**: 只有 7.9% 的情况 experience 修正更接近真实 outcome，但这不足以提升 accuracy。

---

## 13. RECENCY EXPERIMENT

| Window | Accuracy | MAE | Samples |
|--------|----------|-----|---------|
| 10 | 0.6606 | 0.4120 | 10 |
| 50 | 0.6981 | 0.4181 | 50 |
| 100 | 0.7781 | 0.3760 | 100 |
| 250 | 0.6981 | 0.3687 | 250 |
| 500 | 0.6981 | 0.3656 | 500 |
| 1807 | 0.7781 | 0.3592 | 1807 |

**结论**: 全量经验表现最佳，旧经验未污染预测。

---

## 14. PATTERN CONTRIBUTION

```
PATTERN_RUNTIME_STATUS: DEAD
Pattern Store: NOT EXISTING
Pattern Code: EXISTS but NOT INITIALIZED
Contribution: NONE
```

---

## 15. ROOT CAUSE

```
ROOT_CAUSE: Experience is already baked into model's predicted_prob

Technical explanation:
- Model's predicted_prob for each experience IS the empirical rate from training
- Adding "experience evidence" = averaging the same value with itself
- prediction = (1-w) × rate + w × rate = rate (identity transform)
- Therefore, no improvement possible with current design
```

---

## 16. LEARNING SIGNAL

```
LEARNING_SIGNAL: NO_VALIDATED_LEARNING_SIGNAL
```

**五个问题回答**:

| 问题 | 答案 |
|------|------|
| Q1: Experience 是否改变 Prediction? | NO (0%) |
| Q2: Prediction 改变是否更接近 Outcome? | Partial (7.9%) |
| Q3: Experience 是否降低 Error? | NO (0 improvement) |
| Q4: Pattern 是否提供额外信息? | N/A (Pattern 未激活) |
| Q5: 最优 weight 是否优于 0? | NO (所有权重相同) |

---

## 17. RECOMMENDED NEXT EXPERIMENT

```
NEXT_STEP: Redesign experience application mechanism

Current design flaw:
- Experience is stored AND used in the same prediction
- This creates identity transform when re-applied

Suggested approaches:
1. Test with fresh data (no prior experience)
2. Implement online learning (update rates after each event)
3. Add contextual features beyond intent
4. Consider temporal decay for old experiences
```

---

## 18. PRODUCTION CHANGE

```
PRODUCTION_CODE_CHANGED: NO
DATA_CHANGED: NO
CONFIG_CHANGED: NO
DEPENDENCY_CHANGED: NO
```

---

## 19. FINAL VERDICT

```
RESULT: NO_VALIDATED_LEARNING_SIGNAL
```

**实验证明**: 当前 Level 3 的 Experience 机制是一个闭环日志系统，而非学习系统。Experience 被保存但无法提供额外预测改进。

---

## FINAL SUMMARY

```
RESULT: NO_VALIDATED_LEARNING_SIGNAL
EXPERIENCE_COUNT: 2582
TRAIN_COUNT: 1807
HOLDOUT_COUNT: 775

DATA_LEAKAGE: NONE

BASE_ACCURACY: 0.778
EXPERIENCE_ACCURACY: 0.778
PATTERN_ACCURACY: N/A (DEAD)
COMBINED_ACCURACY: 0.778

BASE_ERROR: 0.359
EXPERIENCE_ERROR: 0.359
PATTERN_ERROR: N/A
COMBINED_ERROR: 0.359

BEST_EXPERIENCE_WEIGHT: 0.0 (all equal)
BEST_WEIGHT_IMPROVEMENT: 0.000

REAL_PREDICTION_IMPROVEMENT_RATE: 0.079
EXPERIENCE_INFLUENCE_RATE: 0.000
PATTERN_CONTRIBUTION: NONE
RECENCY_EFFECT: Full data best
HIGH_CONFIDENCE_FAILURE_CHANGE: 0.000

MAIN_FINDING: Experience is already incorporated in predicted_prob
ROOT_CAUSE: Identity transform - experience applied twice
LEARNING_SIGNAL: NO_VALIDATED_LEARNING_SIGNAL

LEVEL_3_5: OPEN (redesign needed)
LEVEL_4: NOT_YET_JUSTIFIED
ML: NOT_REQUIRED

PRODUCTION_CODE_CHANGED: NO
DATA_CHANGED: NO
CONFIG_CHANGED: NO
DEPENDENCY_CHANGED: NO
GIT_STATUS: Unchanged
```

---

## 附录：实验文件

```
/tmp/neurocortex_exp_35b/ (已清理)
├── data_quality.json      # 数据质量统计
├── split_info.json        # 训练/测试划分
├── step3_results.json     # 对照组结果
├── weight_sweep.json      # 权重扫描
├── intent_breakdown.json  # 按意图分解
├── recency_experiment.json # 时效性实验
├── influence_analysis.json # 影响分析
└── final_report.json      # 最终报告
```

---

**实验原则遵守确认**:

✅ 未修改生产代码  
✅ 未修改 Experience 数据  
✅ 未修改配置文件  
✅ 未安装新依赖  
✅ 仅进行离线只读分析  
✅ 实验结束清理临时文件  
