#!/bin/bash
# Quick validation script for new tests

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

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
        echo "   └─ $(wc -l < "$file") lines, $(grep -c 'def test_' "$file") test methods"
    else
        echo "❌ $file - NOT FOUND"
    fi
done

echo ""
echo "📊 Test Statistics:"
total_lines=$(cat "${FILES[@]}" 2>/dev/null | wc -l)
total_tests=$(grep -h 'def test_' "${FILES[@]}" 2>/dev/null | wc -l)
echo "   • Total lines: $total_lines"
echo "   • Total tests: $total_tests"

echo ""
echo "🔍 Checking Python syntax..."
for file in "${FILES[@]}"; do
    if python -m py_compile "$file" 2>/dev/null; then
        echo "✅ $file - Syntax OK"
    else
        echo "❌ $file - Syntax Error"
    fi
done

echo ""
echo "📦 Checking dependencies..."
if python -c "import pytest, yaml" 2>/dev/null; then
    echo "✅ Required dependencies available (pytest, pyyaml)"
else
    echo "⚠️  Some dependencies missing (run: pip install pytest pyyaml)"
fi

echo ""
echo "✅ Validation complete!"
echo ""
echo "To run the new tests:"
echo "  pytest tests/integration/test_pr_agent_config.py -v"
echo "  pytest tests/integration/test_workflow_simplifications.py -v"
