#!/usr/bin/env bash
# Quick validation script for new tests

set -o errexit
set -o nounset
set -o pipefail

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║       New Test Files Validation - Current Branch             ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check if test files exist
echo "📋 Checking test files..."

FILES=(
    "tests/integration/test_pr_agent_config.py"
    "tests/integration/test_workflow_simplifications.py"
)

exit_code=0

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
        echo "   └─ $(wc -l <"$file") lines, $(grep -c 'def test_' "$file" || true) test methods"
    else
        echo "❌ $file - NOT FOUND"
        exit_code=1
    fi
done

echo ""
echo "🔍 Checking Python syntax..."

for file in "${FILES[@]}"; do
    if python -m py_compile "$file" 2>/dev/null; then
        echo "✅ $file - Syntax OK"
    else
        echo "❌ $file - Syntax Error"
        exit_code=1
    fi
done

echo ""
echo "📦 Checking dependencies..."

if python -c "import pytest, yaml" 2>/dev/null; then
    echo "✅ Required dependencies available (pytest, pyyaml)"
else
    echo "⚠️  Some dependencies missing (run: pip install pytest pyyaml)"
    exit_code=1
fi

echo ""
if [ "$exit_code" -eq 0 ]; then
    echo "✅ Validation complete!"
else
    echo "❌ Validation completed with errors (see messages above)."
fi
echo ""
echo "To run the new tests:"
echo "  pytest tests/integration/test_pr_agent_config.py -v"
echo "  pytest tests/integration/test_workflow_simplifications.py -v"

exit "$exit_code"
