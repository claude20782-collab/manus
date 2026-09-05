#!/bin/bash
# Quick Start Script for OpenManus-Web

set -e

echo "🚀 OpenManus-Web Quick Start"
echo "============================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker is available"

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from .env.example..."
    cp .env.example .env
    echo "✅ .env file created"
else
    echo "✅ .env file already exists"
fi

# Create sessions directory
mkdir -p sessions

echo ""
echo "🔨 Building Docker images (this may take a few minutes)..."
if command -v docker-compose &> /dev/null; then
    docker-compose build
else
    docker compose build
fi

echo ""
echo "🚀 Starting services..."
if command -v docker-compose &> /dev/null; then
    docker-compose up -d
else
    docker compose up -d
fi

echo ""
echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
echo ""
echo "📊 Service Status:"
if command -v docker-compose &> /dev/null; then
    docker-compose ps
else
    docker compose ps
fi

echo ""
echo "✅ OpenManus-Web is now running!"
echo ""
echo "📱 Access the application:"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   Ollama:   http://localhost:11434"
echo ""
echo "💡 First-time setup for Ollama:"
echo "   docker exec -it openmanus-web-ollama-1 ollama pull llama3.1"
echo ""
echo "📖 For more information, see README.md"
echo ""
echo "To stop all services:"
if command -v docker-compose &> /dev/null; then
    echo "   docker-compose down"
else
    echo "   docker compose down"
fi
