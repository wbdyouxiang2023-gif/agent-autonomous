#!/usr/bin/env python3
"""NeuroCortex Phase 13 - 使用Pattern系统进行智能预测"""
import sys, json, subprocess, os

NEURO_PATH = '/root/.openclaw/workspace/tools/neurocortex.py'
PATTERN_STORE = '/tmp/patterns_v2.jsonl'

def analyze_with_patterns(message):
    """使用Pattern库进行预测"""
    
    # 1. 基础分析
    result = subprocess.run(
        ['python3', NEURO_PATH, 'analyze', message],
        capture_output=True, text=True, timeout=10
    )
    try:
        base_analysis = json.loads(result.stdout)
    except:
        base_analysis = {'intent': 'general', 'probability': 0.5}
    
    # 2. 检索Pattern
    pattern_confidence = get_pattern_confidence(base_analysis.get('intent', 'general'))
    
    # 3. 融合决策
    if pattern_confidence['found']:
        # 有模式：使用Pattern的预测
        final_prob = pattern_confidence['probability']
        strategy = pattern_confidence['strategy']
        support = pattern_confidence['support_count']
    else:
        # 无模式：使用基础预测
        final_prob = base_analysis.get('probability', 0.5)
        strategy = '常规回应'
        support = 0
    
    # 4. 保存经验
    subprocess.run(['python3', NEURO_PATH, 'save'], capture_output=True)
    
    return {
        'intent': base_analysis.get('intent', 'general'),
        'probability': final_prob,
        'pattern_match': pattern_confidence['found'],
        'strategy': strategy,
        'support_count': support,
        'experience_count': base_analysis.get('experience_count', 0)
    }

def get_pattern_confidence(intent):
    """从Pattern库获取置信度"""
    if not os.path.exists(PATTERN_STORE):
        return {'found': False, 'probability': 0.5, 'strategy': '常规', 'support_count': 0}
    
    patterns = []
    with open(PATTERN_STORE, 'r') as f:
        for line in f:
            try:
                p = json.loads(line.strip())
                if p.get('condition_intent') == intent:
                    patterns.append(p)
            except:
                pass
    
    if not patterns:
        return {'found': False, 'probability': 0.5, 'strategy': '常规', 'support_count': 0}
    
    # 取最新的Pattern
    p = max(patterns, key=lambda x: x.get('created_at', ''))
    
    # 根据支持度确定策略
    support = p.get('support_count', 0)
    success_rate = p.get('success_rate', 0.5)
    
    if success_rate > 0.85:
        strategy = '自信回应'
    elif success_rate > 0.7:
        strategy = '谨慎回应'
    else:
        strategy = '多问澄清'
    
    return {
        'found': True,
        'probability': success_rate,
        'strategy': strategy,
        'support_count': support
    }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'intent': 'general', 'probability': 0.5, 'error': 'No message provided'}))
        sys.exit(1)
    
    message = ' '.join(sys.argv[1:])
    result = analyze_with_patterns(message)
    print(json.dumps(result, ensure_ascii=False))
