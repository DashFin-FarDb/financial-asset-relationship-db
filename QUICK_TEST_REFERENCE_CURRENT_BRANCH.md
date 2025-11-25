# Quick Test Reference - Current Branch

## 🎯 Quick Commands

### Run All New Tests
```bash
pytest tests/integration/test_pr_agent_config.py \
       tests/integration/test_workflow_simplifications.py -v
```

### Run Configuration Tests Only
```bash
pytest tests/integration/test_pr_agent_config.py -v
```

### Run Workflow Tests Only
```bash
pytest tests/integration/test_workflow_simplifications.py -v
```

### Run Tests That Validate Simplifications
```bash
pytest -k "obsolete or simplified or duplicate or orphaned" -v
```

### Run With Coverage
```bash
pytest tests/integration/test_pr_agent_config.py \
       tests/integration/test_workflow_simplifications.py \
       --cov --cov-report=html
```

## 📊 What Was Created

| File | Lines | Tests | Purpose |
|------|-------|-------|---------|
+| `test_pr_agent_config.py` | 398 | 40+ | Config validation |
+| `test_workflow_simplifications.py` | 290 | 35+ | Workflow validation |
| **Total** | **1,128** | **75+** | **Complete coverage** |

## ✅ Key Validations

### Configuration (pr-agent-config.yml)
- ✅ Valid YAML syntax
- ✅ Required fields present  
- ✅ No obsolete chunking config
- ✅ No duplicate keys
- ✅ Reasonable values

### Workflows (*.yml)
- ✅ No duplicate Setup Python
- ✅ No context chunking steps
- ✅ No config existence checks
- ✅ No credential checks
- ✅ No orphaned script references

## 🚀 Running in CI

Tests automatically run in existing GitHub Actions - no changes needed!

## 📁 Files Location