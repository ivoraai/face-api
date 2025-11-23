#!/bin/bash

# Docker build and management script for Face Embedding API

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║ $1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
}

print_info() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Commands
build() {
    print_header "Building Docker Image"
    
    # Use BuildKit for faster builds
    DOCKER_BUILDKIT=1 docker-compose build ${@:2}
    
    print_info "Image built successfully"
}

up() {
    print_header "Starting Services"
    
    local profile=""
    if [[ "$2" == "--celery" ]]; then
        profile="--profile celery"
        print_info "Starting with Celery/Redis"
    fi
    
    docker-compose $profile up -d
    
    print_info "Services started"
    print_info "API: http://localhost:8000"
    print_info "Qdrant: http://localhost:6333/dashboard"
}

down() {
    print_header "Stopping Services"
    
    local remove_volumes=""
    if [[ "$2" == "--clean" ]]; then
        remove_volumes="-v"
        print_warn "Removing volumes (data will be lost)"
    fi
    
    docker-compose down $remove_volumes
    
    print_info "Services stopped"
}

logs() {
    local service="${2:-}"
    
    if [[ -z "$service" ]]; then
        docker-compose logs -f
    else
        docker-compose logs -f "$service"
    fi
}

shell() {
    local service="${2:-face-api}"
    
    print_info "Entering shell for $service"
    docker-compose exec "$service" bash
}

status() {
    print_header "Service Status"
    docker-compose ps
}

health() {
    print_header "Health Check"
    
    echo -e "${BLUE}FastAPI:${NC}"
    curl -s http://localhost:8000/ | python -m json.tool 2>/dev/null || print_error "Not responding"
    
    echo ""
    echo -e "${BLUE}Qdrant:${NC}"
    curl -s http://localhost:6333/health | python -m json.tool 2>/dev/null || print_error "Not responding"
}

restart() {
    local service="${2:-}"
    
    print_header "Restarting Services"
    
    if [[ -z "$service" ]]; then
        docker-compose restart
        print_info "All services restarted"
    else
        docker-compose restart "$service"
        print_info "$service restarted"
    fi
}

rebuild() {
    print_header "Rebuilding Image (No Cache)"
    
    DOCKER_BUILDKIT=1 docker-compose build --no-cache ${@:2}
    
    print_info "Image rebuilt"
}

push() {
    local image="${2:-face-embedding-api:latest}"
    local registry="${3:-}"
    
    print_header "Pushing Docker Image"
    
    if [[ -z "$registry" ]]; then
        print_warn "No registry specified. Usage: ./docker.sh push <image> <registry>"
        return 1
    fi
    
    docker tag "$image" "$registry/$image"
    docker push "$registry/$image"
    
    print_info "Image pushed to $registry"
}

test_api() {
    print_header "Testing API Endpoints"
    
    echo -e "${BLUE}1. Health Check:${NC}"
    curl -s http://localhost:8000/ | python -m json.tool || print_error "Failed"
    
    echo ""
    echo -e "${BLUE}2. List Clusters:${NC}"
    curl -s http://localhost:8000/get-clusters | python -m json.tool || print_error "Failed"
    
    echo ""
    echo -e "${BLUE}3. List Digests:${NC}"
    curl -s http://localhost:8000/get-digests | python -m json.tool || print_error "Failed"
    
    print_info "API tests complete"
}

clean() {
    print_header "Cleaning Docker Resources"
    
    docker system prune -f
    docker volume prune -f
    
    print_info "Docker resources cleaned"
}

help() {
    cat << EOF
${BLUE}Face Embedding API - Docker Management${NC}

Usage: ./docker.sh <command> [options]

Commands:
  ${GREEN}build${NC}              Build Docker image
  ${GREEN}up${NC}                 Start all services
  ${GREEN}down${NC}               Stop services (add --clean to remove volumes)
  ${GREEN}restart${NC}            Restart services
  ${GREEN}rebuild${NC}            Rebuild image without cache
  
  ${GREEN}logs${NC} [service]     View logs (face-api, qdrant, redis)
  ${GREEN}shell${NC} [service]    Enter container shell
  ${GREEN}status${NC}             Show service status
  ${GREEN}health${NC}             Check service health
  
  ${GREEN}test${NC}               Test API endpoints
  ${GREEN}clean${NC}              Clean Docker resources
  ${GREEN}push${NC} <image> <registry>  Push image to registry
  
  ${GREEN}help${NC}               Show this help message

Examples:
  ./docker.sh build                    # Build image
  ./docker.sh up                       # Start services
  ./docker.sh up --celery              # Start with Redis/Celery
  ./docker.sh logs face-api            # View API logs
  ./docker.sh shell face-api           # Enter API container
  ./docker.sh down --clean             # Stop and remove volumes
  ./docker.sh test                     # Test all endpoints
  ./docker.sh push face-embedding-api:latest myregistry.com

EOF
}

# Main script
if [[ $# -eq 0 ]]; then
    help
    exit 1
fi

case "$1" in
    build)
        build "$@"
        ;;
    up)
        up "$@"
        ;;
    down)
        down "$@"
        ;;
    logs)
        logs "$@"
        ;;
    shell)
        shell "$@"
        ;;
    status)
        status
        ;;
    health)
        health
        ;;
    restart)
        restart "$@"
        ;;
    rebuild)
        rebuild "$@"
        ;;
    test)
        test_api
        ;;
    clean)
        clean
        ;;
    push)
        push "$@"
        ;;
    help)
        help
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Run './docker.sh help' for usage information"
        exit 1
        ;;
esac
