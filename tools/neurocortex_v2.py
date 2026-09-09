#!/usr/bin/env python3
"""NeuroCortex 认知大脑 - 深度集成版
改进: 反思机制 + 经验关联 + 人格自适应
"""
import sys, json, subprocess, os
from datetime import datetime

TOOL_PATH = '/root/.openclaw/workspace/tools/neurocortex.py'
PERSONA_PATH = os.path.expanduser('~/.persona.json')
MEMORY_PATH = os.path.expanduser('~/.neurocortex_memory.jsonl')

def run_analysis(message):
    """感知阶段 - 分析意图"""
    result = subprocess.run(
        ['python3', TOOL_PATH, 'analyze', message],
        capture_output=True, text=True, timeout=10
    )
    try:
        return json.loads(result.stdout)
    except:
        return {'intent': 'general', 'probability': 0.5, 'action': 'respond'}

def run_save():
    """学习阶段 - 保存经验"""
    subprocess.run(
        ['python3', TOOL_PATH, 'save'],
        capture_output=True, timeout=5
    )

def run_personality():
    """获取人格状态"""
    result = subprocess.run(
        ['python3', TOOL_PATH, 'personality'],
        capture_output=True, text=True, timeout=5
    )
    return result.stdout

def load_experiences():
    """加载所有经验"""
    if not os.path.exists(MEMORY_PATH):
        return []
    experiences = []
    with open(MEMORY_PATH, 'r') as f:
        for line in f:
            try:
                exp = json.loads(line.strip())
                experiences.append(exp)
            except:
                continue
    return experiences

def find_similar_experiences(intent, message, top_k=3):
    """查找相似经验 - 形成直觉"""
    experiences = load_experiences()
    
    # 按意图过滤
    similar = [e for e in experiences if e.get('intent') == intent]
    
    # 按成功率排序，取最相关的
    similar.sort(key=lambda x: (
        x.get('success', False),
        -x.get('predicted_prob', 0.5)
    ), reverse=True)
    
    return similar[:top_k]

def reflect_on_decision(intent, probability, success_history):
    """反思机制 - 自我评估决策质量"""
    if not success_history:
        return {
            'confidence': 'medium',
            'suggestion': '经验不足，建议谨慎回应',
            'pattern': 'new'
        }
    
    success_rate = sum(1 for e in success_history if e.get('success')) / len(success_history)
    
    if probability > 0.85 and success_rate > 0.8:
        return {
            'confidence': 'high',
            'suggestion': '这是熟练领域，可以自信回应',
            'pattern': 'familiar'
        }
    elif probability < 0.7 or success_rate < 0.6:
        return {
            'confidence': 'low',
            'suggestion': '这是弱项领域，建议多问确认',
            'pattern': 'uncertain'
        }
    else:
        return {
            'confidence': 'medium',
            'suggestion': '正常范围，按常规方式回应',
            'pattern': 'normal'
        }

def adapt_personality(intent, reflection):
    """人格自适应 - 根据情境调整"""
    try:
        with open(PERSONA_PATH, 'r') as f:
            persona = json.load(f)
    except:
        persona = {'traits': [], 'mood': {}}
    
    # 根据反思结果调整人格权重
    if reflection['confidence'] == 'high':
        for trait in persona.get('traits', []):
            if trait['name'] == 'neuroticism':
                trait['value'] = max(0.1, trait['value'] - 0.05)
            elif trait['name'] == 'risk_tolerance':
                trait['value'] = min(1.0, trait['value'] + 0.05)
    elif reflection['confidence'] == 'low':
        for trait in persona.get('traits', []):
            if trait['name'] == 'neuroticism':
                trait['value'] = min(1.0, trait['value'] + 0.05)
            elif trait['name'] == 'conscientiousness':
                trait['value'] = min(1.0, trait['value'] + 0.05)
    
    return persona

def run_cognitive_loop(message):
    """执行完整的认知循环"""
    
    # 1. 感知阶段
    analysis = run_analysis(message)
    intent = analysis.get('intent', 'general')
    probability = analysis.get('probability', 0.5)
    
    # 2. 查找相似经验 - 形成直觉
    similar = find_similar_experiences(intent, message, top_k=3)
    success_history = similar if similar else []
    
    # 3. 反思决策质量
    reflection = reflect_on_decision(intent, probability, success_history)
    
    # 4. 人格自适应
    persona = adapt_personality(intent, reflection)
    
    # 5. 学习阶段
    run_save()
    
    # 6. 获取人格状态
    personality_text = run_personality()
    
    return {
        'intent': intent,
        'probability': probability,
        'action': analysis.get('action', 'respond'),
        'experience_count': analysis.get('experience_count', 0),
        'reflection': reflection,
        'similar_count': len(success_history),
        'personality': personality_text,
        'timestamp': datetime.now().isoformat()
    }

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(json.dumps({'intent': 'general', 'probability': 0.5, 'action': 'noop'}))
        sys.exit(0)
    
    result = run_cognitive_loop(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
