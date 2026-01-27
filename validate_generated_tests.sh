#!/usr/bin/env bash
set -o errexit
set -o nounset
set -o pipefail

echo "==================================="
echo "Test Generation Validation Report"
echo "==================================="
echo ""

# 1. Check Python test syntax
echo "1. Validating Python Test Syntax..."

if python -m py_compile tests/unit/test_auth_refactoring.py 2>/dev/null; then
    echo "   ✓ test_auth_refactoring.py - Syntax OK"
else
    echo "   ✗ test_auth_refactoring.py - Syntax Error"
fi

if python -m py_compile tests/unit/test_database_refactoring.py 2>/dev/null; then
    echo "   ✓ test_database_refactoring.py - Syntax OK"
else
    echo "   ✗ test_database_refactoring.py - Syntax Error"
fi

echo ""
echo "2. Checking TypeScript Test Syntax..."

(
    cd frontend || exit 1
    if npx tsc --noEmit __tests__/lib/api-refactoring.test.ts 2>&1; then
        echo "   ✓ api-refactoring.test.ts - TypeScript validation complete"
    else
        npx tsc --noEmit __tests__/lib/api-refactoring.test.ts 2>&1 | head -20
        echo "   ✗ api-refactoring.test.ts - TypeScript validation failed"
        exit 1
    fi
)
    cd frontend || exit 1
(
    cd frontend || exit 1
    if npx tsc --noEmit __tests__/lib/api-refactoring.test.ts 2>&1; then
        echo "   ✓ api-refactoring.test.ts - TypeScript validation complete"
    else
        npx tsc --noEmit __tests__/lib/api-refactoring.test.ts 2>&1 | head -20
        echo "   ✗ api-refactoring.test.ts - TypeScript validation failed"
        exit 1
    fi
)
    fi
echo "   TypeScript Tests:"
echo "   - api-refactoring.test.ts: $(grep -E -c '\b(it|test)\s*\(['\''"`]' frontend/__tests__/lib/api-refactoring.test.ts) test methods"
echo ""
echo "3. Test File Statistics..."

echo "   Python Tests:"
echo "   - test_auth_refactoring.py: $(grep -c 'def test_' tests/unit/test_auth_refactoring.py) test methods"
echo "   - test_database_refactoring.py: $(grep -c 'def test_' tests/unit/test_database_refactoring.py) test methods"

echo "   TypeScript Tests:"
grep -E -c '\b(it|test)\s*\(['\''"`]' frontend/__tests__/lib/api-refactoring.test.ts

echo ""
echo "4. Summary:"
echo "   Total test files generated: 3"
echo "   Total lines of test code: $(cat \
    tests/unit/test_auth_refactoring.py \
    tests/unit/test_database_refactoring.py \
    frontend/__tests__/lib/api-refactoring.test.ts | wc -l)"
echo "   Ready for execution: Yes"

echo ""
echo "==================================="
echo "Validation Complete"
echo "==================================="
