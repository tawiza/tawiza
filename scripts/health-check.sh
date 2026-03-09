#!/usr/bin/env bash
# =============================================================================
# Tawiza-V2 Health Check
# Verification sante des services en cours d'execution
# Usage: ./scripts/health-check.sh [--verbose]
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

VERBOSE="${1:-}"
HEALTHY=0
UNHEALTHY=0
UNAVAILABLE=0

# =============================================================================
# Helper functions
# =============================================================================

healthy() {
    echo -e "  ${GREEN}[HEALTHY]${NC}     $1"
    HEALTHY=$((HEALTHY + 1))
}

unhealthy() {
    echo -e "  ${RED}[UNHEALTHY]${NC}   $1"
    if [[ -n "${2:-}" ]]; then
        echo -e "                ${CYAN}$2${NC}"
    fi
    UNHEALTHY=$((UNHEALTHY + 1))
}

unavailable() {
    echo -e "  ${YELLOW}[UNAVAILABLE]${NC} $1"
    UNAVAILABLE=$((UNAVAILABLE + 1))
}

header() {
    echo ""
    echo -e "${BOLD}${BLUE}=== $1 ===${NC}"
}

check_http() {
    local name=$1
    local url=$2
    local timeout="${3:-5}"

    local http_code
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout "$timeout" "$url" 2>/dev/null || echo "000")

    if [[ "$http_code" == "000" ]]; then
        unavailable "$name ($url)"
    elif [[ "$http_code" -ge 200 && "$http_code" -lt 400 ]]; then
        healthy "$name ($url) [HTTP $http_code]"
    else
        unhealthy "$name ($url) [HTTP $http_code]"
    fi
}

check_tcp() {
    local name=$1
    local host=$2
    local port=$3
    local timeout="${4:-3}"

    if timeout "$timeout" bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
        healthy "$name ($host:$port)"
    else
        unavailable "$name ($host:$port)"
    fi
}

# =============================================================================
# HTTP Health Endpoints
# =============================================================================

header "HTTP Services"

check_http "FastAPI Backend" "http://localhost:8000/health"
check_http "FastAPI Docs" "http://localhost:8000/docs"
check_http "Next.js Frontend" "http://localhost:3000"
check_http "MinIO API" "http://localhost:9002/minio/health/live"
check_http "MinIO Console" "http://localhost:9003"
check_http "MLflow" "http://localhost:5001"
check_http "Label Studio" "http://localhost:8082"
check_http "Prometheus" "http://localhost:9090/-/ready"
check_http "Grafana" "http://localhost:3003/api/health"
check_http "Prefect" "http://localhost:4200/api/health"
check_http "ChromaDB" "http://localhost:8001/api/v1/heartbeat"
check_http "Skyvern" "http://localhost:8501"
check_http "Ollama" "http://localhost:11434/api/tags"
check_http "Langfuse" "http://localhost:3150"

# =============================================================================
# TCP Services
# =============================================================================

header "TCP Services"

check_tcp "PostgreSQL" "localhost" 5433
check_tcp "Redis" "localhost" 6380
check_tcp "Qdrant" "localhost" 6333
check_tcp "Qdrant gRPC" "localhost" 6334
check_tcp "OTEL Collector" "localhost" 4317

# =============================================================================
# Docker Containers
# =============================================================================

header "Docker Containers"

if command -v docker &>/dev/null && docker info &>/dev/null 2>&1; then
    CONTAINERS=$(docker ps -a --filter "name=tawiza-" --filter "name=openmanus-" --format "{{.Names}}|{{.Status}}|{{.State}}" 2>/dev/null || true)

    if [[ -n "$CONTAINERS" ]]; then
        while IFS='|' read -r name status state; do
            if [[ "$state" == "running" ]]; then
                # Check if container is healthy
                health=$(docker inspect --format='{{.State.Health.Status}}' "$name" 2>/dev/null || echo "none")
                if [[ "$health" == "healthy" ]]; then
                    healthy "$name (healthy)"
                elif [[ "$health" == "unhealthy" ]]; then
                    unhealthy "$name" "Container unhealthy - check: docker logs $name"
                else
                    healthy "$name (running)"
                fi
            else
                unhealthy "$name ($status)"
            fi
        done <<< "$CONTAINERS"
    else
        echo -e "  ${YELLOW}No Tawiza/OpenManus containers found${NC}"
    fi
else
    echo -e "  ${YELLOW}Docker not available${NC}"
fi

# =============================================================================
# Verbose: Connection tests
# =============================================================================

if [[ "$VERBOSE" == "--verbose" || "$VERBOSE" == "-v" ]]; then
    header "Connection Tests (verbose)"

    # Test PostgreSQL connection
    if command -v psql &>/dev/null; then
        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
        if psql "postgresql://tawiza:$(grep DATABASE_PASSWORD "$PROJECT_DIR/.env" 2>/dev/null | cut -d= -f2 | head -1)@localhost:5433/tawiza" -c "SELECT 1;" &>/dev/null 2>&1; then
            healthy "PostgreSQL query OK"
        else
            unhealthy "PostgreSQL query failed"
        fi
    fi

    # Test Redis connection
    if command -v redis-cli &>/dev/null; then
        if redis-cli -p 6380 ping &>/dev/null 2>&1; then
            healthy "Redis PING OK"
        else
            unhealthy "Redis PING failed"
        fi
    fi

    # Test FastAPI readiness
    READY=$(curl -s --connect-timeout 3 "http://localhost:8000/health/ready" 2>/dev/null || echo "")
    if [[ -n "$READY" ]]; then
        healthy "FastAPI readiness: $READY"
    fi
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo -e "${BOLD}${BLUE}=== HEALTH SUMMARY ===${NC}"
echo -e "  ${GREEN}Healthy:${NC}     $HEALTHY"
echo -e "  ${RED}Unhealthy:${NC}   $UNHEALTHY"
echo -e "  ${YELLOW}Unavailable:${NC} $UNAVAILABLE"
echo ""

TOTAL=$((HEALTHY + UNHEALTHY + UNAVAILABLE))
if [[ $TOTAL -eq 0 ]]; then
    echo -e "${YELLOW}No services detected.${NC}"
elif [[ $UNHEALTHY -gt 0 ]]; then
    echo -e "${RED}${BOLD}SOME SERVICES ARE UNHEALTHY${NC}"
    exit 1
elif [[ $UNAVAILABLE -gt $((TOTAL / 2)) ]]; then
    echo -e "${YELLOW}${BOLD}MOST SERVICES UNAVAILABLE${NC} - Are Docker services started?"
    exit 1
else
    echo -e "${GREEN}${BOLD}SERVICES OK${NC}"
    exit 0
fi
