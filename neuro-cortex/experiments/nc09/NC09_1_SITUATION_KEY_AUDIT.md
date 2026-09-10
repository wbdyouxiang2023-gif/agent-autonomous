# NC-09.1 Situation Key Audit

**Date:** 2026-09-09  
**Status:** AUDIT COMPLETE

---

## 1. Root Cause Analysis

### Current Learning Key Structure

```python
# From engine.py line 45-52
def situation_key(situation: ActionLearningSituation) -> str:
    intent = (situation.intent or "").strip().lower()
    return f"intent:{intent}" if intent else "intent:__none__"

def stat_key(situation_key_str: str, action_key: str) -> str:
    return f"{situation_key_str}|action:{action_key}"
```

**Current Key Format:**
```
intent:<task_type>|action:<action_type>
```

**Example Keys from NC-09:**
```
intent:file_search|action:terminal
intent:file_read|action:terminal
intent:general|action:read_file
intent:code_locator|action:terminal
intent:file_read|action:read_file
intent:code_search|action:read_file
```

### The Problem

When V4 classifier returns DIFFERENT task_types for SEMANTICALLY SIMILAR situations:

| Input Situation | V4 Classification | Learning Key |
|----------------|-------------------|--------------|
| "查找函数 find_symbol_1..." | file_search | `intent:file_search\|action:terminal` |
| "定位符号 find_symbol_2..." | code_locator | `intent:code_locator\|action:terminal` |

**Result:** Statistics are fragmented across different keys, preventing cross-situation learning.

---

## 2. Proposed Solution: Canonical Situation Family

### Family Mapping

| task_type | canonical_situation_family |
|-----------|---------------------------|
| code_locator | CODE_LOCATION |
| code_search | CODE_LOCATION |
| file_search | FILE_SEARCH |
| code_inspect | CODE_INSPECTION |
| code_check | CODE_QUALITY |
| file_read | FILE_READ |
| terminal | GENERIC_COMMAND |

### New Learning Key Structure

```python
# Before
stat_key = f"intent:{task_type}|action:{action_type}"

# After
stat_key = f"family:{canonical_family}|action:{action_type}"
```

**Benefits:**
- Semantically similar situations share learning statistics
- Cross-type generalization enabled
- Backward compatible (existing keys still work)

---

## 3. Implementation Plan

### Step 1: Add Family Mapping to Classifier V4
File: `src/neurocortex/perception/classifier_v4.py`

```python
TASK_TYPE_TO_FAMILY = {
    "code_locator": "CODE_LOCATION",
    "code_search": "CODE_LOCATION",
    "file_search": "FILE_SEARCH",
    "code_inspect": "CODE_INSPECTION",
    "code_check": "CODE_QUALITY",
    "file_read": "FILE_READ",
    "terminal": "GENERIC_COMMAND",
}

def get_canonical_family(task_type: str) -> str:
    return TASK_TYPE_TO_FAMILY.get(task_type, task_type.upper())
```

### Step 2: Update Learning Engine
File: `src/neurocortex/action_learning/engine.py`

```python
def situation_key(situation: ActionLearningSituation) -> str:
    """Build canonical situation family key for learning."""
    from neurocortex.perception.classifier_v4 import get_canonical_family
    task_type = (situation.task_type or "").strip().lower()
    family = get_canonical_family(task_type)
    return f"family:{family}" if family else "family:__unknown__"
```

### Step 3: Add Negative Controls
Ensure families are properly separated:
- CODE_LOCATION ≠ CODE_INSPECTION
- CODE_LOCATION ≠ CODE_QUALITY
- FILE_SEARCH ≠ FILE_READ

---

## 4. Expected Impact

### Before Fix
```
S1: "查找函数..." → file_search → key: intent:file_search
S2: "定位符号..." → code_locator → key: intent:code_locator
Result: No cross-learning ❌
```

### After Fix
```
S1: "查找函数..." → file_search → family: CODE_LOCATION
S2: "定位符号..." → code_locator → family: CODE_LOCATION
Result: Cross-learning enabled ✅
```

---

## 5. Verification Plan

1. **Offline Replay:** Use NC-09 statistics to verify key normalization
2. **Real Validation:** Re-run NC-09 experiment with fixed keys
3. **Regression Test:** Ensure existing tests still pass
4. **Negative Control:** Verify unrelated families don't interfere
