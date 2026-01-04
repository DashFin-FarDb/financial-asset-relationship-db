#!/bin/bash
# Run PR Copilot tests
# Usage: ./run_tests.sh [options]

set -e

echo "🧪 Running PR Copilot Tests"
echo "=============================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the script directory and repository root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Set up Python virtual environment for cleaner install
VENV_DIR="$REPO_ROOT/.venv-pr-copilot"

# Cleanup function to ensure deactivation
cleanup() {
    if [ -n "$VIRTUAL_ENV" ]; then
        echo -e "${BLUE}🔌 Deactivating virtual environment...${NC}"
        deactivate 2>/dev/null || true
    fi
}

# Register cleanup on exit
trap cleanup EXIT

# Create or use existing virtual environment
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}🐍 Creating Python virtual environment at $VENV_DIR...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${BLUE}🐍 Using existing virtual environment at $VENV_DIR${NC}"
fi

# Activate virtual environment
echo -e "${BLUE}🔌 Activating virtual environment...${NC}"
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠️  Warning: Virtual environment activation may have failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Virtual environment activated: $VIRTUAL_ENV${NC}"

# Upgrade pip in virtual environment
echo -e "${BLUE}⬆️  Upgrading pip...${NC}"
pip install -q --upgrade pip

# Install dependencies
echo -e "${BLUE}📦 Installing test dependencies...${NC}"
pip install -q pytest pytest-cov

echo -e "${BLUE}📦 Installing PR Copilot dependencies...${NC}"
pip install -q -r "$REPO_ROOT/.github/pr-copilot/scripts/requirements.txt"

echo -e "${GREEN}✅ All dependencies installed${NC}"
echo ""

# Change to repository root for test execution
cd "$REPO_ROOT"

# Run unit tests
echo -e "${BLUE}🧪 Running unit tests...${NC}"
pytest tests/unit/test_pr_copilot_*.py -v

echo ""

# Run integration tests
echo -e "${BLUE}🔗 Running integration tests...${NC}"
pytest tests/integration/test_pr_copilot_workflow.py -v

echo ""
echo -e "${GREEN}✅ All PR Copilot tests passed!${NC}"
echo ""

# Optional: Run with coverage
if [ "$1" == "--coverage" ]; then
    echo -e "${BLUE}📊 Generating coverage report...${NC}"
    pytest tests/unit/test_pr_copilot_*.py \
           tests/integration/test_pr_copilot_workflow.py \
           --cov=.github/pr-copilot/scripts \
           --cov-report=term \
           --cov-report=html
    echo ""
    echo -e "${GREEN}📊 Coverage report generated in htmlcov/index.html${NC}"
fi
