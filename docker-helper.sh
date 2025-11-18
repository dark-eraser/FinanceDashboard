#!/bin/bash
# FinanceTracker Docker Helper Script
# Simplifies common Docker operations

set -e

DOCKER_IMAGE="financetracker"
DOCKER_CONTAINER="financetracker"

show_help() {
    cat << EOF
FinanceTracker Docker Helper

Usage: ./docker-helper.sh [COMMAND]

Commands:
    build           Build the Docker image
    up              Start the application
    down            Stop the application
    restart         Restart the application
    logs            Show application logs
    shell           Access Django shell
    migrate         Run database migrations
    createsuperuser Create a Django admin user
    cleanup         Remove images and volumes
    help            Show this help message

Examples:
    ./docker-helper.sh build
    ./docker-helper.sh up
    ./docker-helper.sh logs
    ./docker-helper.sh shell

EOF
}

build() {
    echo "🔨 Building Docker image..."
    docker-compose build
    echo "✅ Build complete!"
}

up() {
    echo "🚀 Starting application..."
    docker-compose up -d
    echo "✅ Application started!"
    echo "📱 Access at http://localhost:8000/transactions/dashboard/"
}

down() {
    echo "🛑 Stopping application..."
    docker-compose down
    echo "✅ Application stopped!"
}

restart() {
    echo "🔄 Restarting application..."
    docker-compose restart
    echo "✅ Application restarted!"
}

logs() {
    echo "📋 Showing logs (Ctrl+C to exit)..."
    docker-compose logs -f web
}

shell() {
    echo "🐚 Opening Django shell..."
    docker-compose exec web python manage.py shell
}

migrate() {
    echo "🗃️  Running migrations..."
    docker-compose exec web python manage.py migrate
    echo "✅ Migrations complete!"
}

createsuperuser() {
    echo "👤 Creating superuser..."
    docker-compose exec web python manage.py createsuperuser
}

cleanup() {
    echo "🧹 Cleaning up Docker resources..."
    docker-compose down -v
    docker rmi ${DOCKER_IMAGE}:latest 2>/dev/null || true
    echo "✅ Cleanup complete!"
}

# Main script
case "${1:-help}" in
    build)
        build
        ;;
    up)
        build
        up
        ;;
    down)
        down
        ;;
    restart)
        restart
        ;;
    logs)
        logs
        ;;
    shell)
        shell
        ;;
    migrate)
        migrate
        ;;
    createsuperuser)
        createsuperuser
        ;;
    cleanup)
        cleanup
        ;;
    help)
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
