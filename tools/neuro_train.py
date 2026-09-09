#!/usr/bin/env python3
"""NeuroCortex 自动训练脚本
收集对话数据，批量生成训练样本，优化经验库
"""
import sys, os, json, random
from datetime import datetime

STORE_PATH = os.path.expanduser("~/.neurocortex_memory.jsonl")
TRAINING_DATA = os.path.expanduser("~/.neurocortex_training.json")

# 训练模板库
TEMPLATES = {
    "explain": [
        "解释一下{topic}",
        "{topic}是什么",
        "说明{topic}的机制",
        "详细讲解{topic}",
        "科普{topic}",
    ],
    "create": [
        "帮我写一个{task}",
        "创建{task}",
        "开发{task}",
        "实现{task}",
        "制作{task}",
    ],
    "fix": [
        "修复{bug}的问题",
        "解决{error}错误",
        "调试{component}",
        "修复bug:{issue}",
    ],
    "review": [
        "审查{code}的安全性",
        "分析{system}的性能",
        "检查{module}的代码质量",
        "评审{project}的实现",
    ],
    "general": [
        "你好",
        "在吗",
        "今天怎么样",
        "聊聊{topic}",
        "你觉得{topic}怎么样",
    ],
}

TOPICS = ["AI", "机器学习", "神经网络", "大模型", "Agent", "RAG", "向量数据库", "区块链", "云计算", "微服务"]
TASKS = ["API接口", "数据处理脚本", "Web应用", "CLI工具", "自动化流程", "数据分析报告"]
BUGS = ["内存泄漏", "死锁", "竞态条件", "类型错误", "空指针"]
ERRORS = ["404", "500", "Timeout", "Connection refused", "Permission denied"]
COMPONENTS = ["认证模块", "缓存层", "消息队列", "数据库连接", "API网关"]
ISSUES = ["登录失败", "数据丢失", "响应慢", "内存溢出", "服务崩溃"]
CODE = ["核心业务逻辑", "配置管理", "测试用例", "部署脚本", "监控告警"]
SYSTEMS = ["推荐系统", "搜索服务", "支付网关", "用户中心", "消息推送"]
MODULES = ["权限控制", "日志系统", "任务调度", "文件上传", "数据同步"]
PROJECTS = ["电商平台", "社交应用", "内容管理系统", "数据分析平台", "物联网系统"]


def load_existing():
    """加载已有经验"""
    if not os.path.exists(STORE_PATH):
        return []
    experiences = []
    with open(STORE_PATH, 'r') as f:
        for line in f:
            try:
                experiences.append(json.loads(line.strip()))
            except:
                pass
    return experiences


def generate_sample(exp_type=None):
    """生成单个训练样本"""
    if exp_type is None:
        exp_type = random.choice(list(TEMPLATES.keys()))
    
    templates = TEMPLATES[exp_type]
    template = random.choice(templates)
    
    # 填充变量
    input_text = template.format(
        topic=random.choice(TOPICS),
        task=random.choice(TASKS),
        bug=random.choice(BUGS),
        error=random.choice(ERRORS),
        component=random.choice(COMPONENTS),
        issue=random.choice(ISSUES),
        code=random.choice(CODE),
        system=random.choice(SYSTEMS),
        module=random.choice(MODULES),
        project=random.choice(PROJECTS),
    )
    
    # 预测成功率
    base_prob = {
        "explain": 0.9,
        "review": 0.85,
        "general": 0.8,
        "create": 0.6,
        "fix": 0.55,
    }.get(exp_type, 0.7)
    
    # 添加随机波动
    probability = max(0.3, min(1.0, base_prob + random.uniform(-0.15, 0.15)))
    
    # 决定成功/失败
    success = random.random() < probability
    
    import uuid
    from datetime import datetime, timezone
    
    return {
        "experience_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_event_id": str(uuid.uuid4()),
        "raw_input": input_text,
        "intent": exp_type,
        "action_type": random.choice(["respond", "code_edit", "tool_call"]) if success else "respond",
        "predicted_outcome": f"{exp_type}完成",
        "predicted_prob": round(probability, 2),
        "actual_outcome": "done",
        "success": success,
        "prediction_error": round(1 - probability if success else probability, 2),
        "evaluation": "correct" if success else "miss",
        "confidence": 0.56,
        "uncertainty": round(random.uniform(0.05, 0.25), 2),
        "context_tags": [f"intent:{exp_type}", f"action:{random.choice(['respond', 'code_edit', 'tool_call'])}", f"outcome:{'success' if success else 'failure'}", f"eval:{'correct' if success else 'miss'}"],
    }


def batch_generate(count=100, exp_type=None):
    """批量生成训练样本"""
    samples = []
    for _ in range(count):
        samples.append(generate_sample(exp_type))
    return samples


def save_samples(samples, path=None):
    """保存训练样本"""
    if path is None:
        path = TRAINING_DATA
    
    with open(path, 'w') as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)
    
    return len(samples)


def analyze_distribution(experiences):
    """分析经验分布"""
    dist = {}
    for exp in experiences:
        intent = exp.get("intent", "unknown")
        dist[intent] = dist.get(intent, 0) + 1
    return dist


def main():
    print("=== NeuroCortex 自动训练器 ===")
    
    # 加载已有经验
    existing = load_existing()
    print(f"已有经验: {len(existing)} 条")
    
    # 分析分布
    dist = analyze_distribution(existing)
    print(f"当前分布: {dist}")
    
    # 生成补充样本
    # 动态目标：找到当前最小类型的数量作为基准，目标设为该值的1.5倍（最低400）
    total_new = 0
    if dist:
        min_count = min(dist.values())
        target_per_type = max(400, int(min_count * 1.5))
    else:
        target_per_type = 400
    print(f"  目标每类: {target_per_type} 条")
    
    for intent in ["explain", "create", "fix", "review", "general"]:
        current = dist.get(intent, 0)
        needed = max(0, target_per_type - current)
        if needed > 0:
            samples = batch_generate(needed, intent)
            total_new += save_samples(samples)
            print(f"  {intent}: +{needed} 样本")
    
    print(f"\n生成完成: {total_new} 条新样本")
    print(f"训练数据保存至: {TRAINING_DATA}")
    
    # 合并到经验库
    if total_new > 0:
        all_samples = existing + batch_generate(total_new)
        with open(STORE_PATH, 'a') as f:
            for sample in all_samples[len(existing):]:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        print(f"已追加到经验库: +{len(all_samples)-len(existing)} 条，总计 {len(all_samples)} 条")


if __name__ == "__main__":
    main()
