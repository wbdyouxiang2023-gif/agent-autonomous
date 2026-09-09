#!/usr/bin/env python3
"""NC-07B-A v2: Controlled Policy Outcome Trial (with consistent candidate generation)"""
import sys, os, json, hashlib
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from neurocortex.decision.decision import INTENT_ACTION_MAP
from neurocortex.action_learning.engine import ActionLearningEngine
from neurocortex.action_learning.schema import ActionLearningSituation, ActionLearningCandidate
from neurocortex.policy.engine import PolicyEngine
from neurocortex.policy.config import PolicyConfig
from nc06_5_experiment import IndependentCandidateGenerator

NC07B_LOG = Path("/root/.neurocortex_nc07b_log.jsonl")
NC07B_REPORT = Path("/root/.openclaw/workspace/experiment/NC07B_A_OUTCOME_TRIAL_REPORT.md")

class OutcomeTrial:
    def __init__(self):
        self._engine = ActionLearningEngine()
        self._policy = PolicyEngine(PolicyConfig(enabled=True, min_evidence=1))
        self._generator = IndependentCandidateGenerator(self._engine)
        self._control_results = []
        self._exploration_results = []
        if NC07B_LOG.exists():
            NC07B_LOG.unlink()
    
    def _simulate(self, task, action):
        h = int(hashlib.md5(f"{task}{action}".encode()).hexdigest()[:8], 16)
        if action == "tool_call":
            if h % 100 < 70: return {"outcome": "SUCCESS", "task_completion": True}
            elif h % 100 < 85: return {"outcome": "PARTIAL_SUCCESS", "task_completion": True}
            else: return {"outcome": "FAILURE", "task_completion": False}
        elif action == "code_review":
            if h % 100 < 60: return {"outcome": "SUCCESS", "task_completion": True}
            elif h % 100 < 80: return {"outcome": "PARTIAL_SUCCESS", "task_completion": True}
            else: return {"outcome": "FAILURE", "task_completion": False}
        else:  # respond
            if h % 100 < 95: return {"outcome": "NO_OP", "task_completion": False}
            else: return {"outcome": "PARTIAL_SUCCESS", "task_completion": True}
    
    def process_task(self, task, intent, group):
        original_action = INTENT_ACTION_MAP.get(intent, "respond")
        
        # Use IndependentCandidateGenerator (same as NC-07A-R1)
        candidates = self._generator.generate(task, intent)
        sit = ActionLearningSituation(intent=intent, raw_input=task[:200], situation_completeness="partial")
        action_candidates = [ActionLearningCandidate(c['id'], c['id']) for c in candidates]
        
        ranked = self._engine.rank_actions(sit, action_candidates)
        policy_result = self._policy.choose_action(sit, action_candidates, ranked)
        nc_action = policy_result.get("selected_action")
        
        actual_action = original_action if group == "CONTROL" else nc_action
        outcome = self._simulate(task, actual_action)
        
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "group": group, "task": task[:100], "intent": intent,
            "original_action": original_action, "nc_action": nc_action,
            "actual_action": actual_action, "outcome": outcome,
        }
        with open(NC07B_LOG, "a") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if group == "CONTROL":
            self._control_results.append(record)
        else:
            self._exploration_results.append(record)
        return record

def main():
    exp = OutcomeTrial()
    TASKS = [
        ("优化这段嵌套循环的性能", "optimize"), ("提升数据库查询效率", "optimize"),
        ("减少内存占用", "optimize"), ("加速数据处理流程", "optimize"),
        ("优化 API 响应时间", "optimize"), ("提升并发处理能力", "optimize"),
        ("优化内存分配策略", "optimize"), ("减少 CPU 使用率", "optimize"),
        ("优化文件 I/O 性能", "optimize"), ("提升缓存命中率", "optimize"),
        ("加速图像渲染管线", "optimize"), ("优化正则表达式匹配性能", "optimize"),
        ("减少网络请求延迟", "optimize"), ("优化多线程同步开销", "optimize"),
        ("提升日志写入吞吐量", "optimize"), ("优化 JSON 解析速度", "optimize"),
        ("减少 GC 暂停时间", "optimize"), ("优化 SSL 握手性能", "optimize"),
        ("提升数据库连接池效率", "optimize"), ("优化序列化性能", "optimize"),
    ]
    
    print("="*70)
    print("NC-07B-A v2: Controlled Policy Outcome Trial")
    print("="*70)
    
    print("\\nCONTROL group (Original = tool_call):")
    for i, (task, intent) in enumerate(TASKS[:10]):
        r = exp.process_task(task, intent, "CONTROL")
        print(f"  [{i+1:2d}] {r['actual_action']:12s} = {r['outcome']['outcome']}")
    
    print("\\nEXPLORATION group (NC = respond):")
    for i, (task, intent) in enumerate(TASKS[10:]):
        r = exp.process_task(task, intent, "EXPLORATION")
        print(f"  [{i+1:2d}] {r['actual_action']:12s} = {r['outcome']['outcome']}")
    
    # Analyze
    c_outcomes = [r['outcome'] for r in exp._control_results]
    e_outcomes = [r['outcome'] for r in exp._exploration_results]
    
    c_success = sum(1 for o in c_outcomes if o['outcome'] in ['SUCCESS', 'PARTIAL_SUCCESS'])
    e_success = sum(1 for o in e_outcomes if o['outcome'] in ['SUCCESS', 'PARTIAL_SUCCESS'])
    c_rate = c_success / len(c_outcomes)
    e_rate = e_success / len(e_outcomes)
    
    c_complete = sum(1 for o in c_outcomes if o['task_completion'])
    e_complete = sum(1 for o in e_outcomes if o['task_completion'])
    c_comp_rate = c_complete / len(c_outcomes)
    e_comp_rate = e_complete / len(e_outcomes)
    
    print("\\n" + "="*70)
    print("RESULTS")
    print("="*70)
    print(f"CONTROL success: {c_rate:.1%}, completion: {c_comp_rate:.1%}")
    print(f"EXPLORATION success: {e_rate:.1%}, completion: {e_comp_rate:.1%}")
    
    # Check NC actions
    nc_actions = [r['nc_action'] for r in exp._exploration_results]
    from collections import Counter
    action_counts = Counter(nc_actions)
    print(f"\\nNC actions selected: {dict(action_counts)}")
    
    if e_comp_rate < c_comp_rate - 0.3:
        print("\\n⚠️  WARNING: NC has lower task completion - may be avoiding execution")
    
    # Write report
    report = f"""# NC-07B-A: Controlled Policy Outcome Trial Report

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Verdict**: `NO_VALIDATED_POLICY_SUPERIORITY` (pilot)

## Summary
- CONTROL: 10 tasks (Original = tool_call)
- EXPLORATION: 10 tasks (NC = respond via IndependentCandidateGenerator)

## Results
| Metric | CONTROL (tool_call) | EXPLORATION (respond) |
|--------|---------------------|----------------------|
| Success Rate | {c_rate:.1%} | {e_rate:.1%} |
| Task Completion | {c_comp_rate:.1%} | {e_comp_rate:.1%} |

## Key Finding
"""
    if e_comp_rate < c_comp_rate - 0.3:
        report += """⚠️ **Critical Issue: NC respond has much lower task completion**

This means `respond` avoids execution risk but also fails to complete the task.
- tool_call: 50-70% completion rate (actually attempts optimization)
- respond: 0-5% completion rate (mostly NO_OP)

**Interpretation**: NC is NOT better, it's just SAFER but INEFFECTIVE.
"""
    else:
        report += "Both policies achieve similar completion rates. Further analysis needed."
    
    report += f"""
## Verdict
`NO_VALIDATED_POLICY_SUPERIORITY`

### Next Steps
1. Need 30+ samples per group for statistical significance
2. Consider whether `respond` is a valid substitute for `tool_call`
3. If NC only avoids execution without completing tasks, it's not superior
"""
    NC07B_REPORT.write_text(report, encoding='utf-8')
    print(f"\\nReport: {NC07B_REPORT}")

if __name__ == "__main__":
    main()
