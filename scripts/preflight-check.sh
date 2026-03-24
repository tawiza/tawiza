#!/usr/bin/env bash
# =============================================================================
# Tawiza-V2 Preflight Check
# Verification avant demarrage des services
# Usage: ./scripts/preflight-check.sh [--mode standard|minimal|docker]
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Counters
PASS=0
WARN=0
FAIL=0

# Mode (standard, minimal, docker)
MODE="${1:-standard}"
if [[ "$MODE" == "--mode" ]]; then
    MODE="${2:-standard}"
fi

# =============================================================================
# Helper functions
# =============================================================================

ok() {
    echo -e "  ${GREEN}[OK]${NC} $1"
    PASS=$((PASS + 1))
}

warn() {
    echo -e "  ${YELLOW}[WARN]${NC} $1"
    WARN=$((WARN + 1))
}

fail() {
    echo -e "  ${RED}[FAIL]${NC} $1"
    if [[ -n "${2:-}" ]]; then
        echo -e "        ${CYAN}Fix:${NC} $2"
    fi
    FAIL=$((FAIL + 1))
}

header() {
    echo ""
    echo -e "${BOLD}${BLUE}=== $1 ===${NC}"
}

# =============================================================================
# Check prereqs
# =============================================================================

header "Prerequisites"

# Docker
if command -v docker &>/dev/null; then
    DOCKER_VERSION=$(docker --version | head -1)
    ok "Docker: $DOCKER_VERSION"
else
    fail "Docker not installed" "Install Docker: https://docs.docker.com/get-docker/"
fi

# Docker Compose
if command -v docker-compose &>/dev/null || docker compose version &>/dev/null 2>&1; then
    ok "Docker Compose available"
else
    fail "Docker Compose not available" "Install docker-compose or update Docker"
fi

# Python
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 --version)
    ok "Python: $PY_VERSION"
else
    fail "Python3 not installed" "Install Python 3.10+"
fi

# Node.js (for frontend)
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version)
    ok "Node.js: $NODE_VERSION"
else
    warn "Node.js not installed (needed for frontend)"
fi

# Virtual environment
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [[ -d "$PROJECT_DIR/.venv" ]]; then
    ok "Python venv exists: .venv/"
else
    warn "No .venv found"
    echo -e "        ${CYAN}Fix:${NC} python3 -m venv .venv && source .venv/bin/activate && pip install -e ."
fi

# .env file
if [[ -f "$PROJECT_DIR/.env" ]]; then
    ok ".env file exists"
else
    fail ".env file missing" "cp .env.example .env && edit values"
fi

# =============================================================================
# Check ports (mode-dependent)
# =============================================================================

header "Port Availability (mode: $MODE)"

# Define ports by mode
declare -A PORTS
PORTS=(
    ["8000"]="FastAPI Backend"
    ["3000"]="Next.js Frontend"
)

if [[ "$MODE" != "minimal" ]]; then
    PORTS+=(
        ["5433"]="PostgreSQL (Docker)"
        ["6380"]="Redis (Docker)"
        ["9002"]="MinIO API"
        ["9003"]="MinIO Console"
        ["5001"]="MLflow"
        ["8082"]="Label Studio"
        ["9090"]="Prometheus"
        ["3003"]="Grafana"
        ["4200"]="Prefect"
        ["8001"]="ChromaDB"
        ["8501"]="Skyvern"
        ["11434"]="Ollama"
    )
fi

if [[ "$MODE" == "docker" ]]; then
    PORTS+=(
        ["3150"]="Langfuse"
        ["8010"]="FastAPI (Docker)"
        ["6333"]="Qdrant"
        ["6334"]="Qdrant gRPC"
        ["8511"]="Streamlit Evaluator"
        ["8512"]="Streamlit Admin"
        ["8513"]="Streamlit ML"
    )
fi

check_port() {
    local port=$1
    local service=$2
    if ss -tlnp 2>/dev/null | grep -q ":${port} " || \
       lsof -i ":${port}" -sTCP:LISTEN &>/dev/null 2>&1; then
        local pid
        pid=$(lsof -t -i ":${port}" -sTCP:LISTEN 2>/dev/null | head -1 || echo "?")
        local cmd
        cmd=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
        warn "Port $port ($service) in use by PID $pid ($cmd)"
    else
        ok "Port $port ($service) available"
    fi
}

for port in $(echo "${!PORTS[@]}" | tr ' ' '\n' | sort -n); do
    check_port "$port" "${PORTS[$port]}"
done

# =============================================================================
# Check system resources
# =============================================================================

header "System Resources"

# Disk space (need at least 5GB free)
DISK_FREE=$(df -BG "$PROJECT_DIR" | tail -1 | awk '{print $4}' | tr -d 'G')
if [[ "$DISK_FREE" -ge 10 ]]; then
    ok "Disk space: ${DISK_FREE}G free"
elif [[ "$DISK_FREE" -ge 5 ]]; then
    warn "Disk space: ${DISK_FREE}G free (10G+ recommended)"
else
    fail "Disk space: ${DISK_FREE}G free" "Free up disk space (need at least 5G)"
fi

# RAM (need at least 4GB free)
if command -v free &>/dev/null; then
    RAM_FREE=$(free -g | awk '/^Mem:/{print $7}')
    if [[ "$RAM_FREE" -ge 8 ]]; then
        ok "Available RAM: ${RAM_FREE}G"
    elif [[ "$RAM_FREE" -ge 4 ]]; then
        warn "Available RAM: ${RAM_FREE}G (8G+ recommended for all services)"
    else
        warn "Available RAM: ${RAM_FREE}G (may be tight for Docker services)"
    fi
fi

# =============================================================================
# Check Docker state
# =============================================================================

header "Docker State"

if command -v docker &>/dev/null; then
    # Docker daemon running?
    if docker info &>/dev/null 2>&1; then
        ok "Docker daemon running"
    else
        fail "Docker daemon not running" "sudo systemctl start docker"
    fi

    # Existing Tawiza containers
    TAWIZA_CONTAINERS=$(docker ps -a --filter "name=tawiza-" --filter "name=openmanus-" --format "{{.Names}}: {{.Status}}" 2>/dev/null || true)
    if [[ -n "$TAWIZA_CONTAINERS" ]]; then
        echo -e "  ${CYAN}Existing Tawiza containers:${NC}"
        while IFS= read -r line; do
            if echo "$line" | grep -qi "up"; then
                echo -e "    ${GREEN}*${NC} $line"
            else
                echo -e "    ${YELLOW}*${NC} $line"
            fi
        done <<< "$TAWIZA_CONTAINERS"
    else
        ok "No existing Tawiza containers"
    fi
fi

# =============================================================================
# Check .env coherence
# =============================================================================

header "Configuration Coherence"

if [[ -f "$PROJECT_DIR/.env" ]]; then
    # PostgreSQL port
    if grep -q ":5433/" "$PROJECT_DIR/.env" 2>/dev/null; then
        ok "DATABASE_URL uses port 5433 (matches docker-compose)"
    else
        fail "DATABASE_URL not using port 5433" "Update DATABASE_URL port to 5433 in .env"
    fi

    # Redis port
    if grep -q ":6380/" "$PROJECT_DIR/.env" 2>/dev/null; then
        ok "REDIS_URL uses port 6380 (matches docker-compose)"
    else
        fail "REDIS_URL not using port 6380" "Update REDIS_URL port to 6380 in .env"
    fi

    # Grafana port
    if grep -q "GRAFANA_PORT=3003" "$PROJECT_DIR/.env" 2>/dev/null; then
        ok "GRAFANA_PORT=3003 (avoids Next.js conflict)"
    else
        warn "GRAFANA_PORT not set to 3003"
    fi

    # vLLM port
    if grep -q "VLLM_URL=http://localhost:8002" "$PROJECT_DIR/.env" 2>/dev/null; then
        ok "VLLM_URL uses port 8002 (avoids ChromaDB conflict)"
    else
        warn "VLLM_URL not using port 8002"
    fi
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo -e "${BOLD}${BLUE}=== SUMMARY ===${NC}"
echo -e "  ${GREEN}Passed:${NC} $PASS"
echo -e "  ${YELLOW}Warnings:${NC} $WARN"
echo -e "  ${RED}Failed:${NC} $FAIL"
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}${BOLD}PREFLIGHT FAILED${NC} - Fix the issues above before starting."
    exit 1
elif [[ $WARN -gt 0 ]]; then
    echo -e "${YELLOW}${BOLD}PREFLIGHT OK WITH WARNINGS${NC} - Review warnings above."
    exit 0
else
    echo -e "${GREEN}${BOLD}PREFLIGHT PASSED${NC} - Ready to start!"
    exit 0
fi
