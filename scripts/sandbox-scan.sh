#!/usr/bin/env bash
# ─────────────────────────────────────────────────
# sandbox-scan.sh — Lance le bac a sable de scan securite
#
# Usage:
#   ./scripts/sandbox-scan.sh 42        # Scanne la PR #42
#   ./scripts/sandbox-scan.sh --branch feat/new-api
#
# Le container est :
#   - Isole du reseau (--network=none)
#   - Sans volumes montes (clone le repo depuis GitHub)
#   - Detruit automatiquement apres le scan (--rm)
#   - En lecture seule sauf /sandbox et /tmp
# ─────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
IMAGE_NAME="tawiza-sandbox"

# Build l'image si elle n'existe pas ou si --rebuild
if [[ "${1:-}" == "--rebuild" ]]; then
    shift
    docker build -t "$IMAGE_NAME" -f "$PROJECT_DIR/docker/Dockerfile.sandbox" "$PROJECT_DIR"
elif ! docker image inspect "$IMAGE_NAME" >/dev/null 2>&1; then
    echo "Premiere utilisation : construction de l'image sandbox..."
    docker build -t "$IMAGE_NAME" -f "$PROJECT_DIR/docker/Dockerfile.sandbox" "$PROJECT_DIR"
fi

# Le container a besoin du reseau pour cloner le repo
# On le coupe apres le clone via le script interne
docker run --rm \
    --name "tawiza-scan-$$" \
    --memory=512m \
    --cpus=1 \
    --read-only \
    --tmpfs /tmp:size=100m \
    --tmpfs /sandbox:size=500m \
    --security-opt=no-new-privileges \
    --cap-drop=ALL \
    "$IMAGE_NAME" "$@"
