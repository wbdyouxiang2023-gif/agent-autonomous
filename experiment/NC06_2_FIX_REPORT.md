# NC-06.2 FIX Report: Evidence Scope Isolation

## VERDICT: CONTEXTUAL_EVIDENCE_ISOLATION_VALIDATED ✅

---

## 1. 修改文件

| 文件 | 修改内容 |
|------|----------|
| `src/neurocortex/action_learning/config.py` | 添加 `match_level_penalties` 和 `evidence_scope_isolation` 配置 |
| `src/neurocortex/action_learning/engine.py` | 添加 match-level weighting 到 score 计算 |
| `src/neurocortex/policy/engine.py` | 修复 confidence gap 逻辑（禁止负 gap 触发 insufficient） |
| `tests/test_nc06_fix.py` | 新增 9 个 FIX 测试 |

---

## 2. 修改前 Ranking (create intent)

```
code_edit: score=0.4553 support=36 match_level=1
respond:   score=0.6044 support=122 match_level=3
```

**问题**: respond (L3 global) 压过 code_edit (L1 local)

---

## 3. 修改后 Ranking (create intent)

```
code_edit: score=0.4553 raw_score=0.4553 match_penalty=1.0 support=36 match_level=1
respond:   score=0.4231 raw_score=0.6044 match_penalty=0.7 support=122 match_level=3
```

**结果**: code_edit (L1) 现在排名第一

---

## 4. Policy 决策变化

| 状态 | 修改前 | 修改后 |
|------|--------|--------|
| decision_status | insufficient_evidence | decided |
| selected_action | None | code_edit |
| reason | score gap -0.149 < threshold | top-ranked by Action Learning |

---

## 5. 新增测试覆盖

```
tests/test_nc06_fix.py::TestEvidenceScopeIsolation
├── test_local_evidence_beats_global PASSED
├── test_global_fallback_when_local_absent PASSED
└── test_match_level_is_recorded PASSED

tests/test_nc06_fix.py::TestRankingOrder
└── test_ranking_order_preserved PASSED

tests/test_nc06_fix.py::TestPolicyDecision
├── test_create_case_decided PASSED
├── test_optimize_case_decided PASSED
└── test_insufficient_evidence_not_negative_gap PASSED

tests/test_nc06_fix.py::TestAntiSelfReinforcement
├── test_global_does_not_dominate_local PASSED
└── test_local_respond_when_supported PASSED

tests/test_nc06_fix.py::TestRealDataRegression
├── test_real_create_intent PASSED
└── test_all_intents_rank_correctly_intent[fix/optimize/deploy/review/explain/test/general] ALL PASSED
```

**总计**: 17/17 PASSED

---

## 6. 全量回归测试

```
551 passed / 23 failed (pre-existing failures unrelated to this fix)
```

NC-06 FIX 相关测试全部通过，无回归。

---

## 7. Anti-Self-Reinforcement 验证

| 场景 | 修改前 | 修改后 |
|------|--------|--------|
| Global respond=122 vs Local code_edit=36 | global dominate ❌ | local wins ✅ |
| Local respond supported | N/A | local wins ✅ |

**结论**: Evidence scope isolation 生效，L1 > L3

---

## 8. Cumulative Evidence Dominance

| 指标 | 修改前 | 修改后 |
|------|--------|--------|
| cumulative_evidence_dominance | YES ❌ | NO ✅ |

**根因已修复**: match-level penalty 阻止 global evidence 压过 local evidence

---

## 下一步

✅ NC-06.2 完成，可进入 NC-06.3 阶段
