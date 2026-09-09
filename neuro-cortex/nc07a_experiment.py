#!/usr/bin/env python3
"""
NC-07A: Natural Disagreement Collection
-----------------------------------------
Collect natural disagreements between Original Policy and NC Policy
using real tasks WITHOUT modifying production behavior.

Constraints:
- POLICY_SHADOW_ONLY=true
- NC doesn't change real execution
- No artificial evidence creation
- No forced disagreements
- Shadow-only observation
"""
import sys
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from neurocortex.decision.decision import INTENT_ACTION_MAP, BasicDecision
from neurocortex.action_learning.engine import ActionLearningEngine
from neurocortex.action_learning.schema import ActionLearningSituation, ActionLearningCandidate
from neurocortex.action_learning.bridge import ActionLearningBridge
from neurocortex.policy.engine import PolicyEngine
from neurocortex.policy.config import PolicyConfig

# Configuration
NC07A_LOG = Path("/root/.neurocortex_nc07a_log.jsonl")
NC07A_REPORT = Path("/root/.openclaw/workspace/experiment/NC07A_DISAGREEMENT_COLLECTION_REPORT.md")

# Use independent candidate generator (from NC-06.5)
from nc06_5_experiment import IndependentCandidateGenerator


class NC07AExperiment:
    """Natural disagreement collection experiment."""
    
    def __init__(self):
        self._engine = ActionLearningEngine()
        self._bridge = ActionLearningBridge()
        self._policy = PolicyEngine(PolicyConfig(enabled=True, min_evidence=1))
        self._generator = IndependentCandidateGenerator(self._engine)
        self._decision_count = 0
        self._disagreement_count = 0
        self._insufficient_count = 0
        self._log_path = NC07A_LOG
        
        # Clear old log
        if self._log_path.exists():
            self._log_path.unlink()
    
    def _classify_evidence_quality(self, ranking: list[dict], nc_action: str) -> str:
        """Classify evidence quality for a disagreement."""
        nc_ranking = next((r for r in ranking if r['action_key'] == nc_action), None)
        if nc_ranking is None:
            return "INSUFFICIENT"
        
        support = nc_ranking.get('support_count', 0)
        match_level = nc_ranking.get('match_level', 3)
        score = nc_ranking.get('score')
        
        # High evidence: L1 with strong support
        if match_level == 1 and support >= 10 and score and score > 0.5:
            return "HIGH_EVIDENCE"
        
        # Medium evidence: L1 with moderate support or L3 with strong support
        if match_level == 1 and support >= 5:
            return "MEDIUM_EVIDENCE"
        if match_level == 3 and support >= 20 and score and score > 0.4:
            return "MEDIUM_EVIDENCE"
        
        # Low evidence
        if support >= 2:
            return "LOW_EVIDENCE"
        
        return "INSUFFICIENT"
    
    def process_task(self, task: str, expected_intent: str) -> dict:
        """Process a single task and record results."""
        self._decision_count += 1
        
        # Get original action from INTENT_ACTION_MAP
        original_action = INTENT_ACTION_MAP.get(expected_intent, 'respond')
        
        # Build situation
        sit = ActionLearningSituation(
            intent=expected_intent,
            raw_input=task[:200],
            situation_completeness="partial"
        )
        
        # Generate independent candidates (NO original_action constraint)
        independent_candidates = self._generator.generate(task, expected_intent)
        candidate_ids = [c['id'] for c in independent_candidates]
        
        # Convert to ActionLearning format
        action_candidates = [
            ActionLearningCandidate(c['id'], c['id'])
            for c in independent_candidates
        ]
        
        # Rank with ActionLearning
        ranked = self._engine.rank_actions(sit, action_candidates)
        
        # Policy decision
        policy_result = self._policy.choose_action(sit, action_candidates, ranked)
        nc_action = policy_result.get('selected_action')
        
        # Determine disagreement
        disagreement = original_action != nc_action
        
        # Classify evidence quality
        evidence_quality = self._classify_evidence_quality(ranked, nc_action) if disagreement else "N/A"
        
        # Build result record
        record = {
            "task_id": self._decision_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task": task[:100],
            "intent": expected_intent,
            "original_action": original_action,
            "independent_candidates": candidate_ids,
            "nc_action": nc_action,
            "disagreement": disagreement,
            "evidence_quality": evidence_quality if disagreement else "N/A",
            "policy_status": policy_result.get('decision_status'),
            "policy_reason": policy_result.get('decision_reason', '')[:100],
            "ranking": [
                {
                    "action": r["action_key"],
                    "score": round(r["score"], 4) if r["score"] else None,
                    "support": r["support_count"],
                    "match_level": r["match_level"],
                    "evidence_scope": r.get("evidence_scope", "unknown"),
                }
                for r in ranked
            ],
            "outcome": {
                "actual_action": original_action,  # Original executes
                "original_outcome": "OBSERVED",  # Will be filled later
                "nc_outcome": "NOT_OBSERVED",  # Shadow only
            }
        }
        
        # Log to file
        with open(self._log_path, 'a') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
        
        if disagreement:
            self._disagreement_count += 1
            if policy_result.get('decision_status') == 'insufficient_evidence':
                self._insufficient_count += 1
        
        return record
    
    def run(self, tasks: list[tuple[str, str]]) -> dict:
        """Run the experiment with a list of (task, intent) tuples."""
        print(f"\n{'='*70}")
        print("NC-07A: Natural Disagreement Collection")
        print(f"{'='*70}")
        print(f"Total tasks: {len(tasks)}")
        print(f"Log file: {self._log_path}")
        print()
        
        results = []
        disagreements = []
        
        for i, (task, expected_intent) in enumerate(tasks):
            try:
                record = self.process_task(task, expected_intent)
                results.append(record)
                
                status = "DISAGREE" if record['disagreement'] else "agree"
                print(f"[{i+1:3d}/{len(tasks)}] intent={expected_intent:10s} orig={record['original_action']:12s} nc={record['nc_action']:12s} {status}")
                
                if record['disagreement']:
                    disagreements.append(record)
                    
            except Exception as e:
                print(f"[{i+1:3d}/{len(tasks)}] ERROR: {e}")
                results.append({
                    "task_id": i + 1,
                    "error": str(e),
                })
        
        # Generate report
        return self._generate_report(results, disagreements)
    
    def _generate_report(self, results: list[dict], disagreements: list[dict]) -> dict:
        """Generate final report."""
        total = len([r for r in results if 'disagreement' in r])
        disagree_count = len(disagreements)
        agree_count = total - disagree_count
        
        # Classify disagreements by evidence quality
        high_evidence = sum(1 for d in disagreements if d.get('evidence_quality') == 'HIGH_EVIDENCE')
        medium_evidence = sum(1 for d in disagreements if d.get('evidence_quality') == 'MEDIUM_EVIDENCE')
        low_evidence = sum(1 for d in disagreements if d.get('evidence_quality') == 'LOW_EVIDENCE')
        insufficient = sum(1 for d in disagreements if d.get('evidence_quality') == 'INSUFFICIENT')
        
        # Count insufficient evidence decisions
        insufficient_decisions = sum(1 for r in results if r.get('policy_status') == 'insufficient_evidence')
        
        # Determine verdict
        if disagree_count == 0:
            verdict = "NO_NATURAL_DISAGREEMENT_YET"
        elif high_evidence > 0:
            verdict = "NATURAL_DISAGREEMENT_DETECTED"
        elif low_evidence + insufficient > disagree_count * 0.5:
            verdict = "LOW_EVIDENCE_POLICY_DIVERGENCE"
        else:
            verdict = "NATURAL_DISAGREEMENT_DETECTED"
        
        # Write report
        report_lines = [
            "# NC-07A Natural Disagreement Collection Report",
            "",
            f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Verdict**: `{verdict}`",
            "",
            "## Summary",
            f"- Total tasks: {total}",
            f"- Natural agreements: {agree_count} ({agree_count/total*100:.1f}%)",
            f"- Natural disagreements: {disagree_count} ({disagree_count/total*100:.1f}%)",
            f"- Insufficient evidence decisions: {insufficient_decisions}",
            "",
            "## Disagreement Analysis",
            "",
            "| Evidence Quality | Count |",
            "|-----------------|-------|",
            f"| HIGH_EVIDENCE | {high_evidence} |",
            f"| MEDIUM_EVIDENCE | {medium_evidence} |",
            f"| LOW_EVIDENCE | {low_evidence} |",
            f"| INSUFFICIENT | {insufficient} |",
            "",
        ]
        
        if disagreements:
            report_lines.append("## Natural Disagreements Detail")
            report_lines.append("")
            
            for d in disagreements:
                report_lines.append(f"### Task {d['task_id']}: {d['intent']}")
                report_lines.append(f"- Task: {d['task'][:80]}")
                report_lines.append(f"- Original Action: {d['original_action']}")
                report_lines.append(f"- NC Action: {d['nc_action']}")
                report_lines.append(f"- Evidence Quality: {d['evidence_quality']}")
                report_lines.append(f"- Policy Status: {d['policy_status']}")
                report_lines.append(f"- Candidates: {d['independent_candidates']}")
                report_lines.append(f"- Ranking:")
                for r in d['ranking'][:3]:
                    score_str = f"{r['score']:.4f}" if r['score'] else 'None'
                    report_lines.append(f"  - {r['action']}: score={score_str} support={r['support']} L{r['match_level']}")
                report_lines.append("")
        
        report_lines.extend([
            "## Intent Distribution",
            "",
        ])
        
        # Count by intent
        intent_counts = {}
        for r in results:
            if 'intent' in r:
                intent_counts[r['intent']] = intent_counts.get(r['intent'], 0) + 1
        
        for intent, count in sorted(intent_counts.items()):
            report_lines.append(f"- {intent}: {count}")
        
        report_lines.extend([
            "",
            "## Outcome Comparison Dataset",
            "",
            "For each natural disagreement, the outcome dataset records:",
            "",
            "| Field | Value | Explanation |",
            "|-------|-------|-------------|",
            "| actual_action | Original action | What actually executed |",
            "| original_outcome | OBSERVED | Will be filled when outcome known |",
            "| nc_outcome | NOT_OBSERVED | Shadow only, not executed |",
            "",
            "**Note**: Never copy Original outcome to NC outcome.",
            "",
            "## Conclusion",
            "",
            f"The experiment collected {total} natural tasks.",
            f"Found {disagree_count} natural disagreements.",
            "",
            f"**Verdict**: `{verdict}`",
            "",
            "### Next Steps",
            "",
        ])
        
        if verdict == "NO_NATURAL_DISAGREEMENT_YET":
            report_lines.extend([
                "1. Continue collecting more diverse tasks",
                "2. Consider NC-07B: Introduce controlled exploration mode",
                "3. Or R6: Accept current stable state",
            ])
        elif verdict == "NATURAL_DISAGREEMENT_DETECTED":
            report_lines.extend([
                "1. Collect outcomes for disagreements",
                "2. Compare Original vs NC performance",
                "3. Consider NC-07B: Gradual rollout of NC decisions",
            ])
        else:
            report_lines.extend([
                "1. Analyze low-evidence disagreements",
                "2. Determine if evidence thresholds need adjustment",
                "3. Consider NC-07B with higher evidence requirements",
            ])
        
        NC07A_REPORT.write_text('\n'.join(report_lines), encoding='utf-8')
        print(f"\nReport written to: {NC07A_REPORT}")
        
        return {
            "total": total,
            "disagreements": disagree_count,
            "agreements": agree_count,
            "verdict": verdict,
            "evidence_quality": {
                "high": high_evidence,
                "medium": medium_evidence,
                "low": low_evidence,
                "insufficient": insufficient,
            },
            "insufficient_decisions": insufficient_decisions,
        }


def main():
    """Main entry point."""
    # Create experiment
    experiment = NC07AExperiment()
    
    # 100 diverse real tasks
    TASKS = [
        # Create tasks (15)
        ("帮我创建一个 Python 函数来计算斐波那契数列", "create"),
        ("生成一个简单的 REST API 接口", "create"),
        ("写一个读取配置文件的代码", "create"),
        ("创建一个新的类来管理用户会话", "create"),
        ("编写一个日志记录模块", "create"),
        ("实现一个简单的缓存系统", "create"),
        ("创建一个数据解析器", "create"),
        ("写一个 JSON 序列化函数", "create"),
        ("生成一个单元测试模板", "create"),
        ("创建一个新的工具类", "create"),
        ("编写一个文件压缩工具", "create"),
        ("实现一个简单的消息队列", "create"),
        ("创建一个数据库连接池", "create"),
        ("写一个 HTTP 客户端封装", "create"),
        ("生成一个配置文件解析器", "create"),
        
        # Fix tasks (15)
        ("修复这个 TypeError: unsupported operand type(s)", "fix"),
        ("解决 ImportError: No module named 'xxx'", "fix"),
        ("调试一个常见的 NoneType error", "fix"),
        ("修复这段代码的逻辑错误", "fix"),
        ("排查一个死锁问题", "fix"),
        ("解决内存泄漏问题", "fix"),
        ("修复并发编程中的竞争条件", "fix"),
        ("调试异步代码的回调问题", "fix"),
        ("解决序列化时的循环引用", "fix"),
        ("修复数据库连接超时问题", "fix"),
        ("调试权限认证失败的 bug", "fix"),
        ("解决路径处理中的编码问题", "fix"),
        ("修复正则表达式的匹配错误", "fix"),
        ("调试多线程同步问题", "fix"),
        ("解决 API 返回格式不一致的问题", "fix"),
        
        # Optimize tasks (12)
        ("优化这段嵌套循环的性能", "optimize"),
        ("提升数据库查询效率", "optimize"),
        ("减少内存占用", "optimize"),
        ("加速数据处理流程", "optimize"),
        ("优化 API 响应时间", "optimize"),
        ("提升并发处理能力", "optimize"),
        ("优化内存分配策略", "optimize"),
        ("减少 CPU 使用率", "optimize"),
        ("优化文件 I/O 性能", "optimize"),
        ("提升缓存命中率", "optimize"),
        ("优化数据库索引策略", "optimize"),
        ("减少网络请求次数", "optimize"),
        
        # Deploy tasks (10)
        ("部署这个应用到生产环境", "deploy"),
        ("配置 CI/CD 流水线", "deploy"),
        ("运行测试套件", "deploy"),
        ("启动服务并验证健康检查", "deploy"),
        ("发布新版本到市场", "deploy"),
        ("配置负载均衡器", "deploy"),
        ("部署容器化应用", "deploy"),
        ("执行滚动更新", "deploy"),
        ("配置自动扩缩容", "deploy"),
        ("部署监控系统", "deploy"),
        
        # Review tasks (12)
        ("审查这段代码的安全性", "review"),
        ("分析代码复杂度", "review"),
        ("检查依赖版本兼容性", "review"),
        ("评估代码质量", "review"),
        ("查看架构设计合理性", "review"),
        ("审查 API 接口设计", "review"),
        ("分析数据库 schema", "review"),
        ("检查错误处理逻辑", "review"),
        ("评估可维护性", "review"),
        ("审查日志记录规范", "review"),
        ("检查 API 文档完整性", "review"),
        ("分析线程安全性", "review"),
        
        # Explain tasks (12)
        ("解释这个算法的工作原理", "explain"),
        ("说明这段代码的设计模式", "explain"),
        ("讲解 action learning 的原理", "explain"),
        ("阐述架构设计思路", "explain"),
        ("解释错误原因", "explain"),
        ("说明配置参数的含义", "explain"),
        ("讲解依赖注入的工作原理", "explain"),
        ("解释事件循环机制", "explain"),
        ("说明抽象类和接口的区别", "explain"),
        ("讲解事务处理流程", "explain"),
        ("解释正则表达式的匹配原理", "explain"),
        ("说明微服务架构的优势", "explain"),
        
        # Test tasks (12)
        ("运行单元测试套件", "test"),
        ("验证 API 的响应时间", "test"),
        ("检查服务连通性", "test"),
        ("执行集成测试", "test"),
        ("验证数据库连接", "test"),
        ("测试并发处理能力", "test"),
        ("验证错误处理逻辑", "test"),
        ("测试权限控制", "test"),
        ("验证数据一致性", "test"),
        ("测试缓存失效机制", "test"),
        ("验证日志输出格式", "test"),
        ("检查接口兼容性", "test"),
        
        # General tasks (14)
        ("查看当前系统的配置", "general"),
        ("列出所有活跃的连接", "general"),
        ("分析日志文件中的错误", "general"),
        ("搜索包含特定关键词的文件", "general"),
        ("检查磁盘空间使用情况", "general"),
        ("查看系统进程状态", "general"),
        ("分析网络流量", "general"),
        ("检查环境变量配置", "general"),
        ("查看依赖包版本", "general"),
        ("分析代码覆盖率", "general"),
        ("检查配置文件语法", "general"),
        ("查看历史变更记录", "general"),
        ("分析资源使用趋势", "general"),
        ("检查安全更新状态", "general"),
    ]
    
    # Run experiment
    stats = experiment.run(TASKS)
    
    return stats


if __name__ == "__main__":
    stats = main()
    print(f"\n{'='*70}")
    print("EXPERIMENT COMPLETE")
    print(f"{'='*70}")
    print(f"Verdict: {stats['verdict']}")
    print(f"Disagreements: {stats['disagreements']}/{stats['total']}")
    sys.exit(0 if stats['disagreements'] > 0 else 1)
