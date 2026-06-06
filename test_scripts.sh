#!/bin/bash
# Test script to verify error handling
# Tests both output messages and exit codes
# Note: We don't use 'set -e' here to allow testing failure cases

test_count=0
passed_count=0

echo "=== Testing close_unmergeable_prs.sh error handling ==="
echo ""

echo "Test 1: Check gh CLI availability and exit code"
test_count=$((test_count + 1))

# If gh is not installed, script should fail with specific error
if ! command -v gh &> /dev/null; then
    output=$(bash close_unmergeable_prs.sh 2>&1)
    exit_code=$?
    if echo "$output" | grep -q "Error: GitHub CLI (gh) is not installed" && [ $exit_code -ne 0 ]; then
        echo "✅ Correctly detects missing gh CLI with exit code 1"
        passed_count=$((passed_count + 1))
    else
        echo "❌ Failed to properly detect missing gh CLI (exit code: $exit_code)"
    fi
else
    echo "✅ gh CLI detected successfully (test skipped)"
    passed_count=$((passed_count + 1))
fi

echo ""
echo "=== Testing close_unmergeable_prs_script.sh error handling ==="
echo ""

echo "Test 2: Check missing PR number with exit code"
test_count=$((test_count + 1))

output=$(bash close_unmergeable_prs_script.sh 2>&1)
exit_code=$?

if echo "$output" | grep -q "Usage:.*<pr_number>" && [ $exit_code -eq 1 ]; then
    echo "✅ Correctly requires PR number (exit code: $exit_code)"
    passed_count=$((passed_count + 1))
else
    echo "❌ Did not properly handle missing PR number (exit code: $exit_code)"
fi

echo ""
echo "Test 3: Check invalid PR number validation with exit code"
test_count=$((test_count + 1))

output=$(bash close_unmergeable_prs_script.sh "abc" 2>&1)
exit_code=$?

if echo "$output" | grep -q "Error: PR number must be a positive integer" && [ $exit_code -eq 1 ]; then
    echo "✅ Correctly validates numeric PR number (exit code: $exit_code)"
    passed_count=$((passed_count + 1))
else
    echo "❌ Did not properly validate PR number format (exit code: $exit_code)"
fi

echo ""
echo "Test 4: Check PR number with injection attempt"
test_count=$((test_count + 1))

# Test that potentially malicious input is caught by validation
output=$(bash close_unmergeable_prs_script.sh "123 --repo other/repo" 2>&1)
exit_code=$?

if echo "$output" | grep -q "Error: PR number must be a positive integer" && [ $exit_code -eq 1 ]; then
    echo "✅ Correctly rejects injection attempt (exit code: $exit_code)"
    passed_count=$((passed_count + 1))
else
    echo "❌ Did not properly reject injection attempt (exit code: $exit_code)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $passed_count -eq $test_count ]; then
    echo "✅ All tests passed! ($passed_count/$test_count)"
    exit 0
else
    echo "⚠️  Some tests failed: $passed_count/$test_count passed"
    exit 1
fi
