#!/bin/bash

# Agora Consulting AI - Quick Start Script
# This script helps you get the application running quickly

set -e

echo "🚀 Agora Consulting AI - Quick Start"
echo "===================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "   Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    echo "   Visit: https://docs.docker.com/compose/install/"
    exit 1
fi

echo "✓ Docker is installed"
echo "✓ Docker Compose is installed"
echo ""

# Create .env file if it doesn't exist
if [ ! -f backend/.env ]; then
    echo "📝 Creating backend/.env file..."
    cp backend/.env.example backend/.env
    echo "✓ Created backend/.env"
    echo ""
    echo "⚠️  NOTE: Edit backend/.env to add your OpenAI API key for AI features"
    echo ""
fi

# Check if containers are already running
if docker-compose ps | grep -q "Up"; then
    echo "⚠️  Containers are already running. Stopping them first..."
    docker-compose down
    echo ""
fi

echo "🏗️  Building and starting containers..."
echo "   This may take a few minutes on first run..."
echo ""

# Build and start containers
docker-compose up -d --build

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if PostgreSQL is ready
echo "   Checking PostgreSQL..."
until docker-compose exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    echo "   PostgreSQL is starting up..."
    sleep 2
done
echo "   ✓ PostgreSQL is ready"

# Run database migrations
echo ""
echo "🗄️  Running database migrations..."
docker-compose exec -T backend alembic upgrade head

# Create admin user
echo ""
echo "👤 Creating admin user..."
docker-compose exec -T backend python scripts/create_admin.py

echo ""
echo "=============================================="
echo "✅ Agora Consulting AI is ready!"
echo "=============================================="
echo ""
echo "📍 Access the application:"
echo "   Frontend:  http://localhost:5173"
echo "   Backend:   http://localhost:8000"
echo "   API Docs:  http://localhost:8000/docs"
echo ""
echo "🔐 Login:"
echo "   Email:     admin@example.com"
echo "   Password:  (check init_db.py output or set ADMIN_PASSWORD env var)"
echo ""
echo "📚 Useful commands:"
echo "   View logs:        docker-compose logs -f"
echo "   Stop services:    docker-compose down"
echo "   Restart services: docker-compose restart"
echo "   View status:      docker-compose ps"
echo ""
echo "💡 Need help? Check README.md for more information"
echo ""
