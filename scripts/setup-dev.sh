#!/bin/bash
# Tawiza-V2 Development Environment Setup
# Usage: ./scripts/setup-dev.sh

set -e

echo "🚀 Tawiza-V2 Dev Setup"
echo "===================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Check prerequisites
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}❌ $1 not found${NC}"
        return 1
    else
        echo -e "${GREEN}✅ $1 found${NC}"
        return 0
    fi
}

echo ""
echo "📋 Checking prerequisites..."
check_command python3
check_command node
check_command bun || echo -e "${YELLOW}   Install: curl -fsSL https://bun.sh/install | bash${NC}"
check_command uv || echo -e "${YELLOW}   Install: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"

# Setup Python environment
echo ""
echo "🐍 Setting up Python environment..."
export PATH="$HOME/.local/bin:$PATH"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv .venv --python 3.13
fi

echo "Installing dependencies..."
uv sync

# Setup frontend
echo ""
echo "⚛️ Setting up frontend..."
export PATH="$HOME/.bun/bin:$PATH"
cd frontend
bun install
cd ..

# Check .env
echo ""
echo "🔐 Checking environment..."
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating from template...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}   Please edit .env with your credentials${NC}"
else
    echo -e "${GREEN}✅ .env exists${NC}"
fi

# Security check
echo ""
echo "🛡️ Running security scan..."
.venv/bin/bandit -r src/ -ll -q 2>/dev/null | head -20 || true

echo ""
echo "===================="
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "To start development:"
echo "  Backend:  source .venv/bin/activate && uvicorn src.interfaces.api.main:app --reload --port 8000"
echo "  Frontend: cd frontend && npm run dev"
echo ""
