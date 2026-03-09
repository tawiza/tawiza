#!/bin/bash
# Tawiza v2.0.3 - Automated Development Environment Setup
# Optimized for AMD self-hosted with uv + ruff (Phase 1 tools)

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Logging functions
log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# Banner
echo "================================================================================"
echo "  Tawiza v2.0.3 - Development Environment Setup"
echo "  AMD Self-Hosted Stack + Python 3.13 + uv + ruff"
echo "================================================================================"
echo ""

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing_deps=()

    # Required commands
    local required_cmds=("git" "python3" "curl" "docker" "docker-compose")

    for cmd in "${required_cmds[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            missing_deps+=("$cmd")
        fi
    done

    if [ ${#missing_deps[@]} -gt 0 ]; then
        log_error "Missing required dependencies: ${missing_deps[*]}"
        log_info "Please install missing dependencies and try again"
        exit 1
    fi

    # Check Python version
    python_version=$(python3 --version | cut -d' ' -f2)
    if [[ ! "$python_version" =~ ^3\.(11|12|13) ]]; then
        log_warning "Python $python_version detected. Python 3.11+ recommended"
    else
        log_success "Python $python_version detected"
    fi

    log_success "All prerequisites installed"
}

# Install uv package manager (Phase 1)
install_uv() {
    log_info "Installing uv package manager (10-100x faster than pip)..."

    if command -v uv &> /dev/null; then
        uv_version=$(uv --version | cut -d' ' -f2)
        log_success "uv already installed (v$uv_version)"
        return 0
    fi

    # Install uv
    curl -LsSf https://astral.sh/uv/install.sh | sh

    # Add to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"

    if command -v uv &> /dev/null; then
        log_success "uv installed successfully"
    else
        log_error "uv installation failed"
        exit 1
    fi
}

# Create Python virtual environment
setup_venv() {
    log_info "Setting up Python virtual environment with uv..."

    if [ -d "venv" ]; then
        log_warning "Virtual environment already exists"
        read -p "Recreate it? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf venv
        else
            log_info "Keeping existing virtual environment"
            return 0
        fi
    fi

    # Create venv with uv
    uv venv venv --python python3.13

    log_success "Virtual environment created"
}

# Install dependencies
install_dependencies() {
    log_info "Installing dependencies with uv (fast!)..."

    # Activate venv
    source venv/bin/activate

    # Install from requirements.txt using uv
    uv pip install -r requirements.txt

    # Install development dependencies
    uv pip install pre-commit pytest pytest-asyncio pytest-cov pytest-mock ruff mypy bandit

    log_success "Dependencies installed"
}

# Setup pre-commit hooks
setup_precommit() {
    log_info "Setting up pre-commit hooks..."

    source venv/bin/activate

    # Install pre-commit hooks
    pre-commit install
    pre-commit install --hook-type commit-msg

    log_success "Pre-commit hooks installed"

    # Optionally run on all files
    read -p "Run pre-commit on all files now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_info "Running pre-commit on all files..."
        pre-commit run --all-files || log_warning "Some pre-commit checks failed (this is normal on first run)"
    fi
}

# Setup environment variables
setup_environment() {
    log_info "Setting up environment variables..."

    if [ ! -f .env ]; then
        if [ -f .env.example ]; then
            cp .env.example .env
            log_success "Created .env from .env.example"
            log_warning "Please update .env with your configuration"
        else
            log_warning "No .env.example found, creating minimal .env"
            cat > .env << 'EOF'
# Tawiza v2.0.3 Environment Configuration
APP_ENV=development
DEBUG=true

# Database
DATABASE__URL=postgresql+asyncpg://tawiza:password@localhost:5432/tawiza

# Redis
REDIS__URL=redis://localhost:6379/0

# Ollama
OLLAMA__BASE_URL=http://localhost:11434

# Vector Database (Phase 2)
VECTORDB__ENABLED=true
VECTORDB__EMBEDDING_MODEL=nomic-embed-text

# LitServe (Phase 3)
# Set to true to use LitServe for optimized LLM serving
OLLAMA__USE_LITSERVE=false
OLLAMA__LITSERVE_URL=http://localhost:8001
EOF
            log_success "Created minimal .env file"
            log_warning "Please update .env with your configuration"
        fi
    else
        log_success ".env file already exists"
    fi
}

# Setup local services (Docker)
setup_services() {
    log_info "Setting up local services with Docker..."

    if [ ! -f docker-compose.yml ]; then
        log_warning "No docker-compose.yml found, skipping service setup"
        return 0
    fi

    # Check if Docker is running
    if ! docker info &> /dev/null; then
        log_error "Docker is not running. Please start Docker and try again"
        return 1
    fi

    # Start services
    log_info "Starting Docker services (PostgreSQL, Redis, etc.)..."
    docker-compose up -d

    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 5

    # Check PostgreSQL
    if docker-compose exec -T postgres pg_isready -U tawiza &> /dev/null; then
        log_success "PostgreSQL is ready"
    else
        log_warning "PostgreSQL might not be ready yet"
    fi

    log_success "Docker services started"
}

# Initialize database
initialize_database() {
    log_info "Initializing database..."

    # Check if database is accessible
    if ! docker-compose exec -T postgres pg_isready -U tawiza &> /dev/null; then
        log_warning "PostgreSQL not ready, skipping database initialization"
        return 0
    fi

    source venv/bin/activate

    # Run migrations (if alembic is set up)
    if [ -d "migrations" ]; then
        log_info "Running database migrations..."
        alembic upgrade head || log_warning "Migration failed (might be normal if not set up yet)"
    fi

    log_success "Database initialized"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."

    local dirs=(
        "logs"
        "data"
        "outputs"
        "models"
        "uploads"
    )

    for dir in "${dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            mkdir -p "$dir"
        fi
    done

    log_success "Directories created"
}

# Display summary
display_summary() {
    echo ""
    echo "================================================================================"
    echo "  ✅ Development Environment Setup Complete!"
    echo "================================================================================"
    echo ""
    echo "📋 Next Steps:"
    echo ""
    echo "1. Activate the virtual environment:"
    echo "   source venv/bin/activate"
    echo ""
    echo "2. Update your .env file with proper configuration:"
    echo "   nano .env"
    echo ""
    echo "3. Start the development server:"
    echo "   uvicorn src.interfaces.api.main:app --reload --host 0.0.0.0 --port 8000"
    echo ""
    echo "4. (Optional) Start LitServe for optimized LLM serving (Phase 3):"
    echo "   python scripts/start_litserve.py"
    echo ""
    echo "5. Visit the API documentation:"
    echo "   http://localhost:8000/docs"
    echo ""
    echo "================================================================================"
    echo "  Useful Commands"
    echo "================================================================================"
    echo ""
    echo "Run tests:"
    echo "  pytest tests/ -v"
    echo ""
    echo "Run linting:"
    echo "  ruff check src/"
    echo ""
    echo "Format code:"
    echo "  ruff format src/"
    echo ""
    echo "Run pre-commit manually:"
    echo "  pre-commit run --all-files"
    echo ""
    echo "View Docker logs:"
    echo "  docker-compose logs -f"
    echo ""
    echo "================================================================================"
}

# Main execution
main() {
    check_prerequisites
    install_uv
    setup_venv
    install_dependencies
    setup_precommit
    setup_environment
    create_directories

    # Optional: setup Docker services
    read -p "Setup Docker services (PostgreSQL, Redis, etc.)? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        setup_services
        initialize_database
    fi

    display_summary
}

# Run main function
main "$@"
