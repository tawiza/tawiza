#!/usr/bin/env bash
# =============================================================================
# Tawiza-V2 Port Checker
# Utilitaire rapide pour verifier l'occupation des ports
# Usage:
#   ./scripts/check-ports.sh --all          # Tous les ports Tawiza
#   ./scripts/check-ports.sh 8000 3000      # Ports specifiques
#   ./scripts/check-ports.sh --conflicts    # Verifier seulement les ports a risque
# =============================================================================

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'
BOLD='\033[1m'

# All Tawiza ports with descriptions
declare -A ALL_PORTS=(
    ["3000"]="Next.js Frontend"
    ["3001"]="Reflex Frontend"
    ["3003"]="Grafana"
    ["3150"]="Langfuse"
    ["4200"]="Prefect"
    ["4317"]="OTEL Collector"
    ["5001"]="MLflow"
    ["5433"]="PostgreSQL"
    ["6333"]="Qdrant"
    ["6334"]="Qdrant gRPC"
    ["6380"]="Redis"
    ["8000"]="FastAPI Backend"
    ["8001"]="ChromaDB"
    ["8002"]="vLLM"
    ["8004"]="Reflex Backend API"
    ["8010"]="FastAPI (Docker)"
    ["8082"]="Label Studio"
    ["8085"]="OpenManus Core"
    ["8501"]="Skyvern"
    ["8511"]="Streamlit Evaluator"
    ["8512"]="Streamlit Admin"
    ["8513"]="Streamlit ML"
    ["9002"]="MinIO API"
    ["9003"]="MinIO Console"
    ["9090"]="Prometheus"
    ["11434"]="Ollama"
)

# Conflict-prone ports
CONFLICT_PORTS=(3000 3003 5433 6380 8001 8002 8004 3150)

check_port() {
    local port=$1
    local desc="${2:-}"

    # Try ss first, fallback to lsof
    local result=""
    if command -v ss &>/dev/null; then
        result=$(ss -tlnp 2>/dev/null | grep ":${port} " || true)
    fi

    if [[ -z "$result" ]] && command -v lsof &>/dev/null; then
        result=$(lsof -i ":${port}" -sTCP:LISTEN -P -n 2>/dev/null || true)
    fi

    if [[ -n "$result" ]]; then
        # Extract PID and command
        local pid cmd
        pid=$(lsof -t -i ":${port}" -sTCP:LISTEN 2>/dev/null | head -1 || echo "?")
        cmd=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")

        if [[ -n "$desc" ]]; then
            printf "  ${RED}%-6s${NC} %-25s ${YELLOW}IN USE${NC}  PID=%-8s CMD=%s\n" "$port" "$desc" "$pid" "$cmd"
        else
            printf "  ${RED}%-6s${NC} ${YELLOW}IN USE${NC}  PID=%-8s CMD=%s\n" "$port" "$pid" "$cmd"
        fi
        return 1
    else
        if [[ -n "$desc" ]]; then
            printf "  ${GREEN}%-6s${NC} %-25s ${GREEN}FREE${NC}\n" "$port" "$desc"
        else
            printf "  ${GREEN}%-6s${NC} ${GREEN}FREE${NC}\n" "$port"
        fi
        return 0
    fi
}

# =============================================================================
# Main
# =============================================================================

echo -e "${BOLD}${BLUE}Tawiza-V2 Port Status${NC}"
echo ""

IN_USE=0
FREE=0

if [[ "${1:-}" == "--all" ]]; then
    # All Tawiza ports
    for port in $(echo "${!ALL_PORTS[@]}" | tr ' ' '\n' | sort -n); do
        if ! check_port "$port" "${ALL_PORTS[$port]}"; then
            IN_USE=$((IN_USE + 1))
        else
            FREE=$((FREE + 1))
        fi
    done

elif [[ "${1:-}" == "--conflicts" ]]; then
    # Only conflict-prone ports
    echo -e "${YELLOW}Checking conflict-prone ports:${NC}"
    echo ""
    for port in "${CONFLICT_PORTS[@]}"; do
        desc="${ALL_PORTS[$port]:-unknown}"
        if ! check_port "$port" "$desc"; then
            IN_USE=$((IN_USE + 1))
        else
            FREE=$((FREE + 1))
        fi
    done

elif [[ $# -gt 0 ]]; then
    # Specific ports
    for port in "$@"; do
        desc="${ALL_PORTS[$port]:-}"
        if ! check_port "$port" "$desc"; then
            IN_USE=$((IN_USE + 1))
        else
            FREE=$((FREE + 1))
        fi
    done

else
    # No args: show usage
    echo "Usage:"
    echo "  $0 --all              Check all Tawiza ports"
    echo "  $0 --conflicts        Check conflict-prone ports only"
    echo "  $0 8000 3000 5433     Check specific ports"
    echo ""
    echo "All Tawiza ports:"
    for port in $(echo "${!ALL_PORTS[@]}" | tr ' ' '\n' | sort -n); do
        echo "  $port  ${ALL_PORTS[$port]}"
    done
    exit 0
fi

# Summary
echo ""
echo -e "${BOLD}Total: ${GREEN}$FREE free${NC}, ${RED}$IN_USE in use${NC}"
