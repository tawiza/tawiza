#!/usr/bin/env bash
# ─────────────────────────────────────────────────
# pr-scan.sh — Analyse securite d'une PR tawiza
# Usage: pr-scan <numero_pr> | pr-scan --branch <branche>
# ─────────────────────────────────────────────────
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

REPO="https://github.com/tawiza/tawiza.git"
WORKDIR="/sandbox/repo"

header() { echo -e "\n${CYAN}${BOLD}══ $1 ══${NC}"; }
pass()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
warn()   { echo -e "  ${YELLOW}[!!]${NC} $1"; }
fail()   { echo -e "  ${RED}[FAIL]${NC} $1"; }

# ── Parse args ──
PR_NUM=""
BRANCH=""
if [[ "${1:-}" == "--branch" ]]; then
    BRANCH="${2:-}"
    [[ -z "$BRANCH" ]] && { echo "Usage: pr-scan --branch <branche>"; exit 1; }
elif [[ "${1:-}" =~ ^[0-9]+$ ]]; then
    PR_NUM="$1"
else
    echo "Usage: pr-scan <numero_pr> | pr-scan --branch <branche>"
    exit 1
fi

ISSUES=0

# ── Clone ──
header "Clone du repo"
git clone --depth=50 "$REPO" "$WORKDIR" 2>/dev/null
cd "$WORKDIR"

if [[ -n "$PR_NUM" ]]; then
    echo "Fetching PR #$PR_NUM..."
    git fetch origin "pull/$PR_NUM/head:pr-$PR_NUM" 2>/dev/null
    git checkout "pr-$PR_NUM" 2>/dev/null
    CHANGED_FILES=$(git diff --name-only main..."pr-$PR_NUM" 2>/dev/null || true)
elif [[ -n "$BRANCH" ]]; then
    git checkout "$BRANCH" 2>/dev/null
    CHANGED_FILES=$(git diff --name-only main..."$BRANCH" 2>/dev/null || true)
fi

echo "Fichiers modifies: $(echo "$CHANGED_FILES" | wc -l)"

# ── 1. Trojan Source (caracteres Unicode invisibles) ──
header "Trojan Source — caracteres invisibles"
TROJAN=$(grep -rPn '[\x{200B}\x{200C}\x{200D}\x{2060}\x{FEFF}\x{202A}-\x{202E}\x{2066}-\x{2069}]' \
    --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" \
    --include="*.json" --include="*.yml" --include="*.yaml" --include="*.toml" \
    --exclude-dir=".git" --exclude-dir="node_modules" --exclude-dir=".venv" \
    . 2>/dev/null || true)
if [[ -n "$TROJAN" ]]; then
    fail "Caracteres Unicode invisibles detectes !"
    echo "$TROJAN"
    ISSUES=$((ISSUES + 10))
else
    pass "Aucun caractere invisible"
fi

# ── 2. Gitleaks (secrets) ──
header "Gitleaks — secrets"
if gitleaks detect --source . --no-git -q 2>/dev/null; then
    pass "Aucun secret detecte"
else
    fail "Secrets detectes par gitleaks !"
    gitleaks detect --source . --no-git -v 2>/dev/null || true
    ISSUES=$((ISSUES + 10))
fi

# ── 3. Fichiers sensibles ──
header "Fichiers sensibles"
SENSITIVE=$(find . -not -path "./.git/*" -not -path "./node_modules/*" -not -path "./.venv/*" \
    \( -name "*.env" -not -name ".env.example" -not -name ".env.local.example" \) \
    -o -name "*.secret" -o -name "*.key" -o -name "*.pem" -o -name "id_rsa*" \
    -o -name "*.p12" -o -name "*.pfx" -o -name "*.keystore" 2>/dev/null || true)
if [[ -n "$SENSITIVE" ]]; then
    fail "Fichiers sensibles trouves :"
    echo "$SENSITIVE"
    ISSUES=$((ISSUES + 10))
else
    pass "Aucun fichier sensible"
fi

# ── 4. Ruff (lint + securite) ──
header "Ruff — lint Python"
RUFF_OUT=$(ruff check src/ 2>/dev/null || true)
RUFF_COUNT=$(echo "$RUFF_OUT" | grep -c "^" 2>/dev/null || echo "0")
if [[ "$RUFF_COUNT" -gt 1 ]]; then
    warn "$RUFF_COUNT problemes ruff"
    echo "$RUFF_OUT" | head -20
    ISSUES=$((ISSUES + 1))
else
    pass "Code propre"
fi

# ── 5. Bandit (securite Python) ──
header "Bandit — vulnerabilites Python"
BANDIT_OUT=$(bandit -r src/ -ll -q 2>/dev/null || true)
HIGH_COUNT=$(echo "$BANDIT_OUT" | grep -c "Severity: High" 2>/dev/null || echo "0")
MED_COUNT=$(echo "$BANDIT_OUT" | grep -c "Severity: Medium" 2>/dev/null || echo "0")

if [[ "$HIGH_COUNT" -gt 0 ]]; then
    fail "$HIGH_COUNT vulnerabilites HIGH"
    echo "$BANDIT_OUT" | grep -A2 "Severity: High"
    ISSUES=$((ISSUES + HIGH_COUNT * 5))
else
    pass "Aucune vulnerabilite HIGH"
fi
if [[ "$MED_COUNT" -gt 0 ]]; then
    warn "$MED_COUNT vulnerabilites MEDIUM"
fi

# ── 6. Patterns suspects ──
# NOTE: ces grep detectent des patterns dangereux dans le code ANALYSE
# Le script lui-meme n'utilise aucune de ces fonctions dangereuses
header "Patterns suspects"

# Execution de code dynamique (Bandit B307/B102)
DYNAMIC_EXEC=$(grep -rEn '\beval\b\s*\(|\bexec\b\s*\(' --include="*.py" \
    --exclude-dir=".git" --exclude-dir=".venv" . 2>/dev/null \
    | grep -v '^\s*#' | grep -v 'test' || true)
if [[ -n "$DYNAMIC_EXEC" ]]; then
    warn "Execution de code dynamique detectee :"
    echo "$DYNAMIC_EXEC" | head -5
    ISSUES=$((ISSUES + 3))
fi

# subprocess shell=True (Bandit B602)
SHELL_TRUE=$(grep -rn 'shell\s*=\s*True' --include="*.py" \
    --exclude-dir=".git" --exclude-dir=".venv" . 2>/dev/null || true)
if [[ -n "$SHELL_TRUE" ]]; then
    warn "subprocess avec shell=True :"
    echo "$SHELL_TRUE" | head -5
    ISSUES=$((ISSUES + 3))
fi

# Deserialization non securisee (Bandit B301)
# Recherche de fonctions de deserialisation qui acceptent des donnees arbitraires
UNSAFE_DESER=$(grep -rEn 'pickle\.(load|loads)\b|torch\.load\b|yaml\.load\s*\(' --include="*.py" \
    --exclude-dir=".git" --exclude-dir=".venv" . 2>/dev/null || true)
if [[ -n "$UNSAFE_DESER" ]]; then
    warn "Deserialization non securisee detectee :"
    echo "$UNSAFE_DESER" | head -5
    ISSUES=$((ISSUES + 5))
fi

# References au repo prive
PRIV=$(grep -rn 'MPtoO-V2\|hamidedefr/MPtoO\|mptoo-v2\|moltbot-secure' \
    --include="*.py" --include="*.ts" --include="*.tsx" --include="*.js" --include="*.md" \
    --exclude-dir=".git" --exclude-dir="node_modules" . 2>/dev/null || true)
if [[ -n "$PRIV" ]]; then
    fail "References au repo prive detectees !"
    echo "$PRIV" | head -5
    ISSUES=$((ISSUES + 5))
fi

# ── Rapport final ──
echo ""
echo -e "${BOLD}════════════════════════════════════════${NC}"
if [[ "$ISSUES" -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}  RESULTAT : PROPRE (score: 0)${NC}"
elif [[ "$ISSUES" -lt 10 ]]; then
    echo -e "${YELLOW}${BOLD}  RESULTAT : ATTENTION (score: $ISSUES)${NC}"
else
    echo -e "${RED}${BOLD}  RESULTAT : PROBLEMES DETECTES (score: $ISSUES)${NC}"
fi
echo -e "${BOLD}════════════════════════════════════════${NC}"
echo ""
echo "Score: 0 = propre, <10 = mineur, >=10 = a investiguer"
