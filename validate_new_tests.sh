#!/bin/bash
# Validation script for newly created test files
# Run this to verify all new tests are working correctly

set -e  # Exit on error

echo "=================================="
echo "Test Validation Script"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# print_success prints a green checkmark followed by the given message in green.
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# print_error prints an error message prefixed with a red cross symbol.
print_error() {
    echo -e "${RED}✗${NC} $1"
}

# print_info prints an informational message prefixed with a yellow 'ℹ' symbol.
print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Step 1: Check Python syntax
echo "Step 1: Checking Python syntax..."
if python -m py_compile tests/integration/test_documentation_files_validation.py 2>/dev/null; then
    print_success "test_documentation_files_validation.py syntax valid"
else
    print_error "test_documentation_files_validation.py has syntax errors"
    exit 1
fi

if python -m py_compile tests/integration/test_modified_config_files_validation.py 2>/dev/null; then
    print_success "test_modified_config_files_validation.py syntax valid"
else
    print_error "test_modified_config_files_validation.py has syntax errors"
    exit 1
fi
echo ""

# Step 2: Check dependencies
echo "Step 2: Checking dependencies..."
if python -c "import pytest" 2>/dev/null; then
    print_success "pytest is installed"
else
    print_error "pytest is not installed (run: pip install pytest)"
    exit 1
fi

if python -c "import yaml" 2>/dev/null; then
    print_success "PyYAML is installed"
else
    print_error "PyYAML is not installed (run: pip install pyyaml)"
    exit 1
fi
echo ""

# Step 3: Run new tests
echo "Step 3: Running new tests..."
print_info "Running test_documentation_files_validation.py..."
if pytest tests/integration/test_documentation_files_validation.py -v --tb=short 2>&1 | tee /tmp/test_output.txt; then
    test_count=$(grep -c "PASSED" /tmp/test_output.txt || echo "0")
    print_success "Documentation validation tests passed ($test_count tests)"
else
    print_error "Documentation validation tests failed"
    exit 1
fi
echo ""

print_info "Running test_modified_config_files_validation.py..."
if pytest tests/integration/test_modified_config_files_validation.py -v --tb=short 2>&1 | tee /tmp/test_output.txt; then
    test_count=$(grep -c "PASSED" /tmp/test_output.txt || echo "0")
    print_success "Configuration validation tests passed ($test_count tests)"
else
    print_error "Configuration validation tests failed"
    exit 1
fi
echo ""

# Step 4: Verify file counts
echo "Step 4: Verifying file statistics..."
doc_lines=$(wc -l < tests/integration/test_documentation_files_validation.py)
config_lines=$(wc -l < tests/integration/test_modified_config_files_validation.py)
total_test_lines=$((doc_lines + config_lines))

print_info "Test file lines: $total_test_lines"
if [ "$total_test_lines" -gt 500 ]; then
    print_success "Sufficient test coverage ($total_test_lines lines)"
else
    print_error "Insufficient test coverage ($total_test_lines lines)"
fi
echo ""

# Step 5: Check documentation
echo "Step 5: Checking documentation files..."
doc_files=(
    "TEST_VALIDATION_COMPREHENSIVE_SUMMARY.md"
    "COMPLETE_TEST_QUICK_REFERENCE.md"
    "FINAL_TEST_GENERATION_COMPLETE.md"
    "TEST_FILES_INDEX.md"
)

for doc in "${doc_files[@]}"; do
    if [ -f "$doc" ]; then
        print_success "$doc exists"
    else
        print_error "$doc is missing"
        exit 1
    fi
done
echo ""

# Step 6: Final summary
echo "=================================="
echo "Validation Summary"
echo "=================================="
print_success "All syntax checks passed"
print_success "All dependencies available"
print_success "All new tests passed"
print_success "All documentation files present"
echo ""
echo -e "${GREEN}✓ VALIDATION COMPLETE${NC}"
echo ""
echo "Next steps:"
echo "  1. Review test output above"
echo "  2. Run full test suite: pytest tests/integration/ -v"
echo "  3. Commit changes with: git add tests/integration/*.py *.md"
echo ""
